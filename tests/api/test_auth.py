"""Auth uçları (`/auth/*`, Taha'nın şekli — sözleşme §3 kutusu). Davranış stub, şekil birebir."""

import pytest
from fastapi.testclient import TestClient

from tests.api.helpers import TOKEN_KEYS, USER_KEYS, assert_error_shape, assert_utc

NEW_USER = {"email": "taha@test.com", "password": "min8karakter", "full_name": "Taha Yılmaz"}
DEMO_LOGIN = {"email": "demo@aerospace.local", "password": "demo12345"}


def _register(c: TestClient, **override) -> dict:
    r = c.post("/auth/register", json={**NEW_USER, **override})
    assert r.status_code == 201, r.text
    return r.json()


def _login(c: TestClient, email: str, password: str) -> dict:
    r = c.post("/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return r.json()


# --------------------------------------------------------------------------------------------- register


def test_register_201_user_out_taha_shape(client: TestClient) -> None:
    body = _register(client)
    assert set(body) == USER_KEYS  # role yok, parola/özet yok
    assert isinstance(body["id"], int) and body["id"] > 1  # 1 = seed demo kullanıcı
    assert body["email"] == "taha@test.com"
    assert body["full_name"] == "Taha Yılmaz"
    assert_utc(body["created_at"])


def test_register_duplicate_email_409(client: TestClient) -> None:
    _register(client)
    err = assert_error_shape(client.post("/auth/register", json=NEW_USER), 409, "CONFLICT")
    assert err["details"] is None


def test_register_duplicate_email_case_insensitive_409(client: TestClient) -> None:
    _register(client)
    assert_error_shape(client.post("/auth/register", json={**NEW_USER, "email": "TAHA@Test.com"}), 409, "CONFLICT")


def test_register_seed_demo_email_409(client: TestClient) -> None:
    r = client.post("/auth/register", json={**NEW_USER, "email": DEMO_LOGIN["email"]})
    assert_error_shape(r, 409, "CONFLICT")


def test_register_password_7_chars_422(client: TestClient) -> None:
    err = assert_error_shape(client.post("/auth/register", json={**NEW_USER, "password": "1234567"}),
                             422, "VALIDATION_ERROR")
    assert isinstance(err["details"], list) and err["details"]
    assert any("password" in d["field"] for d in err["details"])


@pytest.mark.parametrize("payload", [
    {"password": "min8karakter", "full_name": "X"},
    {**NEW_USER, "email": "gecersiz-eposta"},
    {**NEW_USER, "full_name": ""},
])
def test_register_invalid_body_422(client: TestClient, payload: dict) -> None:
    assert_error_shape(client.post("/auth/register", json=payload), 422, "VALIDATION_ERROR")


# --------------------------------------------------------------------------------------------- login


def test_login_registered_user_200_token_response(client: TestClient) -> None:
    _register(client)
    body = _login(client, NEW_USER["email"], NEW_USER["password"])
    assert set(body) == TOKEN_KEYS  # Taha'nın şekli: user yok
    assert body["token_type"] == "bearer"
    assert body["expires_in"] == 3600
    assert body["access_token"] and body["refresh_token"]
    assert body["access_token"] != body["refresh_token"]


def test_login_seed_demo_account_200(client: TestClient) -> None:
    body = _login(client, **DEMO_LOGIN)
    assert set(body) == TOKEN_KEYS


@pytest.mark.parametrize("creds", [
    {"email": "demo@aerospace.local", "password": "yanlis-parola"},
    {"email": "yok@aerospace.local", "password": "demo12345"},
])
def test_login_wrong_credentials_401(client: TestClient, creds: dict) -> None:
    err = assert_error_shape(client.post("/auth/login", json=creds), 401, "UNAUTHORIZED")
    assert "demo12345" not in err["message"]


def test_login_missing_field_422(client: TestClient) -> None:
    assert_error_shape(client.post("/auth/login", json={"email": "demo@aerospace.local"}), 422, "VALIDATION_ERROR")


# --------------------------------------------------------------------------------------------- refresh


def test_refresh_valid_200(client: TestClient) -> None:
    tokens = _login(client, **DEMO_LOGIN)
    r = client.post("/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert r.status_code == 200, r.text
    assert set(r.json()) == TOKEN_KEYS
    assert r.json()["token_type"] == "bearer"


@pytest.mark.parametrize("token", ["sahte-token", "stub-refresh.1.0000", "eyJhbGciOiJIUzI1NiJ9.x.y"])
def test_refresh_fake_token_401(client: TestClient, token: str) -> None:
    assert_error_shape(client.post("/auth/refresh", json={"refresh_token": token}), 401, "UNAUTHORIZED")


def test_refresh_with_access_token_401(client: TestClient) -> None:
    tokens = _login(client, **DEMO_LOGIN)
    r = client.post("/auth/refresh", json={"refresh_token": tokens["access_token"]})
    assert_error_shape(r, 401, "UNAUTHORIZED")


def test_refresh_missing_body_422(client: TestClient) -> None:
    assert_error_shape(client.post("/auth/refresh", json={}), 422, "VALIDATION_ERROR")


# --------------------------------------------------------------------------------------------- me


def test_me_auth_disabled_returns_demo_user(client: TestClient) -> None:
    r = client.get("/auth/me")
    assert r.status_code == 200
    body = r.json()
    assert set(body) == USER_KEYS
    assert body["id"] == 1
    assert body["email"] == "demo@aerospace.local"
    assert_utc(body["created_at"])


# --------------------------------------------------------------------------------------------- AUTH_ENABLED=true


@pytest.fixture
def secure_client(make_client) -> TestClient:
    return make_client(AUTH_ENABLED="true")


@pytest.mark.parametrize("path", ["/auth/me", "/api/v1/standards", "/api/v1/reports", "/api/v1/chat/conversations"])
def test_auth_enabled_no_token_401(secure_client: TestClient, path: str) -> None:
    assert_error_shape(secure_client.get(path), 401, "UNAUTHORIZED")


def test_auth_enabled_bad_token_401(secure_client: TestClient) -> None:
    r = secure_client.get("/api/v1/standards", headers={"Authorization": "Bearer stub-access.1.yanlis"})
    assert_error_shape(r, 401, "UNAUTHORIZED")


def test_auth_enabled_refresh_token_not_accepted_as_access(secure_client: TestClient) -> None:
    tokens = _login(secure_client, **DEMO_LOGIN)
    r = secure_client.get("/auth/me", headers={"Authorization": f"Bearer {tokens['refresh_token']}"})
    assert_error_shape(r, 401, "UNAUTHORIZED")


def test_auth_enabled_public_endpoints_open(secure_client: TestClient) -> None:
    for path in ("/", "/health", "/api/v1/meta/enums"):
        assert secure_client.get(path).status_code == 200, path


def test_auth_enabled_login_token_works(secure_client: TestClient) -> None:
    user = _register(secure_client)
    tokens = _login(secure_client, NEW_USER["email"], NEW_USER["password"])
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    me = secure_client.get("/auth/me", headers=headers)
    assert me.status_code == 200
    assert me.json() == user
    r = secure_client.get("/api/v1/standards", headers=headers)
    assert r.status_code == 200
    assert r.json()["total"] == 3


def test_auth_enabled_refreshed_token_works(secure_client: TestClient) -> None:
    tokens = _login(secure_client, **DEMO_LOGIN)
    new = secure_client.post("/auth/refresh", json={"refresh_token": tokens["refresh_token"]}).json()
    r = secure_client.get("/auth/me", headers={"Authorization": f"Bearer {new['access_token']}"})
    assert r.status_code == 200
    assert r.json()["email"] == DEMO_LOGIN["email"]


def test_auth_enabled_engineer_cannot_create_standard_403(secure_client: TestClient) -> None:
    _register(secure_client)  # yeni kullanıcı ENGINEER
    tokens = _login(secure_client, NEW_USER["email"], NEW_USER["password"])
    r = secure_client.post(
        "/api/v1/standards", headers={"Authorization": f"Bearer {tokens['access_token']}"},
        json={"code": "ISO-9001", "title": "Quality", "standard_type": "INTL"},
    )
    assert_error_shape(r, 403, "FORBIDDEN")


def test_auth_enabled_demo_admin_can_create_standard(secure_client: TestClient) -> None:
    tokens = _login(secure_client, **DEMO_LOGIN)
    r = secure_client.post(
        "/api/v1/standards", headers={"Authorization": f"Bearer {tokens['access_token']}"},
        json={"code": "ISO-9001", "title": "Quality", "standard_type": "INTL"},
    )
    assert r.status_code == 201, r.text


def test_auth_enabled_reports_are_per_user(secure_client: TestClient) -> None:
    # Yeni kullanıcı seed raporunu (demo kullanıcının) göremez.
    _register(secure_client)
    tokens = _login(secure_client, NEW_USER["email"], NEW_USER["password"])
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    assert secure_client.get("/api/v1/reports", headers=headers).json()["total"] == 0
    assert_error_shape(secure_client.get("/api/v1/reports/1", headers=headers), 404, "NOT_FOUND")


# --------------------------------------------------------------------------------------------- yalnız boşluk metinler (düzeltilmiş bulgu)


def test_register_whitespace_only_full_name_422(client: TestClient) -> None:
    r = client.post("/auth/register", json={**NEW_USER, "full_name": "   "})
    assert_error_shape(r, 422, "VALIDATION_ERROR")


def test_password_with_spaces_not_trimmed(client: TestClient) -> None:
    pw = "  bosluklu parola  "
    _register(client, password=pw)
    assert set(_login(client, NEW_USER["email"], pw)) == TOKEN_KEYS
    assert_error_shape(client.post("/auth/login", json={"email": NEW_USER["email"], "password": pw.strip()}),
                       401, "UNAUTHORIZED")


def test_register_email_and_name_trimmed(client: TestClient) -> None:
    body = _register(client, email="  taha@test.com  ", full_name="  Taha Yılmaz  ")
    assert body["email"] == "taha@test.com" and body["full_name"] == "Taha Yılmaz"
    assert set(_login(client, "  taha@test.com ", NEW_USER["password"])) == TOKEN_KEYS


def test_refresh_whitespace_only_token_422(client: TestClient) -> None:
    assert_error_shape(client.post("/auth/refresh", json={"refresh_token": "   "}), 422, "VALIDATION_ERROR")
