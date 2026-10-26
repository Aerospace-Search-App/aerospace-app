"""Faz 1: sistem endpoint'leri, tek tip hata formatı ve get_current_user (sözleşme §0, §2)."""

from typing import Any

import pytest
from fastapi import Depends, FastAPI, HTTPException
from fastapi.testclient import TestClient
from pydantic import BaseModel

from src.core.config import Settings, get_settings
from src.core.deps import get_current_user
from src.core.errors import (
    AppError,
    BadRequestError,
    ConflictError,
    ForbiddenError,
    LLMUnavailableError,
    NotFoundError,
    PayloadTooLargeError,
    UnauthorizedError,
    UnsupportedFileError,
)
from src.domain.entities import User
from src.domain.enums import SearchMode, StandardType

# --------------------------------------------------------------------------------------------- yardımcılar


def assert_error_shape(response, status: int, code: str) -> dict[str, Any]:
    """Sözleşme §0: `{"error": {"code", "message", "details"}}` ve başka hiçbir anahtar yok."""
    assert response.status_code == status, response.text
    assert response.headers["content-type"].startswith("application/json")
    body = response.json()
    assert set(body.keys()) == {"error"}, body
    err = body["error"]
    assert set(err.keys()) == {"code", "message", "details"}, err
    assert err["code"] == code
    assert isinstance(err["message"], str) and err["message"].strip()
    text = response.text
    assert "Traceback" not in text
    assert 'File "' not in text
    return err


# --------------------------------------------------------------------------------------------- GET /


def test_root_returns_app_info(client: TestClient) -> None:
    r = client.get("/")
    assert r.status_code == 200
    assert r.json() == {
        "app": "Aerospace Compliance Platform",
        "version": "1.1.0",
        "docs": "/docs",
        "api": "/api/v1",
    }


def test_root_wrong_method_405(client: TestClient) -> None:
    r = client.post("/")
    assert_error_shape(r, 405, "METHOD_NOT_ALLOWED")


# --------------------------------------------------------------------------------------------- GET /health


def test_health_ok_mock_mode(client: TestClient) -> None:
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert set(body.keys()) == {"status", "version", "checks"}
    assert body["status"] == "ok"
    assert body["version"] == "1.1.0"
    assert body["checks"] == {"database": "ok", "search": "mock", "llm": "mock"}


def test_health_reflects_configured_providers(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    get_settings.cache_clear()
    from main import create_app

    with TestClient(create_app()) as c:
        r = c.get("/health")
    assert r.status_code == 200
    assert r.json()["checks"]["llm"] == "gemini"
    assert r.json()["checks"]["search"] == "mock"


def test_health_wrong_method_405(client: TestClient) -> None:
    r = client.post("/health")
    err = assert_error_shape(r, 405, "METHOD_NOT_ALLOWED")
    assert err["details"] is None


# --------------------------------------------------------------------------------------------- GET /api/v1/meta/enums


def test_meta_enums_matches_contract(client: TestClient) -> None:
    r = client.get("/api/v1/meta/enums")
    assert r.status_code == 200
    body = r.json()
    assert set(body.keys()) == {
        "standard_types", "standard_statuses", "index_statuses", "requirement_categories",
        "report_types", "report_statuses", "verdicts", "search_modes", "limits",
    }
    assert body["standard_types"] == ["MIL", "CIVIL", "INTL"]
    assert body["standard_statuses"] == ["ACTIVE", "SUPERSEDED", "ARCHIVED"]
    assert body["index_statuses"] == ["NOT_INDEXED", "PENDING", "PROCESSING", "INDEXED", "FAILED"]
    assert body["requirement_categories"] == ["ENVIRONMENTAL", "EMC", "SOFTWARE", "STRUCTURAL", "SAFETY"]
    assert body["report_types"] == ["DESIGN", "TEST", "QUAL", "COMPLIANCE"]
    assert body["report_statuses"] == ["UPLOADED", "PROCESSING", "READY", "FAILED"]
    assert body["search_modes"] == ["semantic", "keyword", "hybrid"]
    assert body["limits"] == {"max_upload_mb": 50, "max_top_k": 20, "max_page_size": 100}


def test_meta_enums_verdict_labels(client: TestClient) -> None:
    verdicts = client.get("/api/v1/meta/enums").json()["verdicts"]
    assert verdicts == [
        {"value": "COMPLIANT", "label_tr": "Uyumlu", "label_en": "Compliant"},
        {"value": "PARTIAL", "label_tr": "Kısmen Uyumlu", "label_en": "Partially Compliant"},
        {"value": "NON_COMPLIANT", "label_tr": "Uyumsuz", "label_en": "Non-Compliant"},
        {"value": "INSUFFICIENT", "label_tr": "Yetersiz Bilgi", "label_en": "Insufficient Information"},
    ]
    # "Kısmen" içindeki ı gerçekten U+0131 (noktasız ı) olmalı, Latin i ya da Kiril karakter değil.
    assert "\u0131" in verdicts[1]["label_tr"]
    for v in verdicts:
        assert set(v.keys()) == {"value", "label_tr", "label_en"}
        assert not any("\u0400" <= ch <= "\u04ff" for ch in v["label_tr"] + v["label_en"])


def test_meta_enums_utf8_response(client: TestClient) -> None:
    r = client.get("/api/v1/meta/enums")
    assert "Kısmen Uyumlu".encode("utf-8") in r.content


def test_meta_enums_limits_follow_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MAX_UPLOAD_MB", "10")
    get_settings.cache_clear()
    from main import create_app

    with TestClient(create_app()) as c:
        assert c.get("/api/v1/meta/enums").json()["limits"]["max_upload_mb"] == 10


def test_meta_enums_wrong_method_405(client: TestClient) -> None:
    assert_error_shape(client.delete("/api/v1/meta/enums"), 405, "METHOD_NOT_ALLOWED")


# --------------------------------------------------------------------------------------------- 404


@pytest.mark.parametrize("path", ["/olmayan-yol", "/api/v1/olmayan", "/api/v2/meta/enums", "/api/v1/meta/enums/x"])
def test_unknown_path_404_uniform(client: TestClient, path: str) -> None:
    err = assert_error_shape(client.get(path), 404, "NOT_FOUND")
    assert "details" in err


# --------------------------------------------------------------------------------------------- geçici route'lar


class _Body(BaseModel):
    name: str
    top_k: int


_ERRORS: dict[str, type[AppError]] = {
    "bad": BadRequestError,
    "unauth": UnauthorizedError,
    "forbidden": ForbiddenError,
    "notfound": NotFoundError,
    "conflict": ConflictError,
    "toolarge": PayloadTooLargeError,
    "unsupported": UnsupportedFileError,
    "llm": LLMUnavailableError,
}


def _add_probe_routes(app: FastAPI) -> None:
    """Hata handler'larını sınamak için uygulamaya sadece testte geçici route'lar ekler."""

    @app.get("/_probe/validate")
    def _validate(limit: int, mode: SearchMode, kind: StandardType = StandardType.MIL) -> dict[str, Any]:
        return {"limit": limit, "mode": mode, "kind": kind}

    @app.post("/_probe/body")
    def _body(body: _Body) -> dict[str, Any]:
        return body.model_dump()

    @app.get("/_probe/crash")
    def _crash() -> None:
        raise RuntimeError("GIZLI_SIR_12345 C:/secret/path.py line 42")

    @app.get("/_probe/zero")
    def _zero() -> None:
        _ = 1 / 0

    @app.get("/_probe/http/{status}")
    def _http(status: int) -> None:
        raise HTTPException(status_code=status, detail="ham detay GIZLI_DETAY")

    @app.get("/_probe/app-error/{name}")
    def _app_error(name: str) -> None:
        raise _ERRORS[name]("Test mesajı: ğüşıöç İ", details={"id": 7})

    @app.get("/_probe/app-error-default/{name}")
    def _app_error_default(name: str) -> None:
        raise _ERRORS[name]()

    @app.get("/_probe/me")
    def _me(user: User = Depends(get_current_user)) -> dict[str, Any]:
        return {"id": user.id, "email": user.email, "role": user.role}


@pytest.fixture
def probe_client(app: FastAPI):
    _add_probe_routes(app)
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


# --------------------------------------------------------------------------------------------- 422


def test_probe_happy_path(probe_client: TestClient) -> None:
    r = probe_client.get("/_probe/validate", params={"limit": 5, "mode": "hybrid"})
    assert r.status_code == 200
    assert r.json() == {"limit": 5, "mode": "hybrid", "kind": "MIL"}


def _assert_validation_details(err: dict[str, Any]) -> list[dict[str, Any]]:
    details = err["details"]
    assert isinstance(details, list) and details
    for item in details:
        assert set(item.keys()) == {"field", "message"}, item
        assert isinstance(item["field"], str) and item["field"]
        assert isinstance(item["message"], str) and item["message"]
    return details


def test_422_query_int_and_enum(probe_client: TestClient) -> None:
    r = probe_client.get("/_probe/validate", params={"limit": "abc", "mode": "SEMANTIC", "kind": "XYZ"})
    err = assert_error_shape(r, 422, "VALIDATION_ERROR")
    details = _assert_validation_details(err)
    fields = {d["field"] for d in details}
    assert fields == {"query.limit", "query.mode", "query.kind"}
    # Ham pydantic alanları sızmamalı.
    for key in ('"input"', '"ctx"', '"loc"', '"type"', '"url"'):
        assert key not in r.text


def test_422_missing_required_query(probe_client: TestClient) -> None:
    err = assert_error_shape(probe_client.get("/_probe/validate"), 422, "VALIDATION_ERROR")
    fields = {d["field"] for d in _assert_validation_details(err)}
    assert fields == {"query.limit", "query.mode"}


def test_422_body_wrong_types(probe_client: TestClient) -> None:
    r = probe_client.post("/_probe/body", json={"name": 1, "top_k": "çok"})
    err = assert_error_shape(r, 422, "VALIDATION_ERROR")
    fields = {d["field"] for d in _assert_validation_details(err)}
    assert fields == {"body.name", "body.top_k"}
    for key in ('"input"', '"ctx"'):
        assert key not in r.text


def test_422_malformed_json(probe_client: TestClient) -> None:
    r = probe_client.post("/_probe/body", content=b'{"name": "x", ', headers={"content-type": "application/json"})
    err = assert_error_shape(r, 422, "VALIDATION_ERROR")
    _assert_validation_details(err)


def test_422_missing_body(probe_client: TestClient) -> None:
    err = assert_error_shape(probe_client.post("/_probe/body"), 422, "VALIDATION_ERROR")
    _assert_validation_details(err)


# --------------------------------------------------------------------------------------------- 500


@pytest.mark.parametrize("path", ["/_probe/crash", "/_probe/zero"])
def test_500_internal_error_hides_details(probe_client: TestClient, path: str) -> None:
    r = probe_client.get(path)
    err = assert_error_shape(r, 500, "INTERNAL_ERROR")
    assert err["details"] is None
    for leak in ("GIZLI_SIR_12345", "secret", "RuntimeError", "ZeroDivisionError", "division by zero", ".py"):
        assert leak not in r.text


# --------------------------------------------------------------------------------------------- HTTPException


@pytest.mark.parametrize(
    ("status", "code"),
    [(400, "BAD_REQUEST"), (401, "UNAUTHORIZED"), (403, "FORBIDDEN"), (404, "NOT_FOUND"), (413, "PAYLOAD_TOO_LARGE")],
)
def test_framework_http_exception_uniform(probe_client: TestClient, status: int, code: str) -> None:
    r = probe_client.get(f"/_probe/http/{status}")
    assert_error_shape(r, status, code)


# --------------------------------------------------------------------------------------------- AppError alt sınıfları


@pytest.mark.parametrize(
    ("name", "status", "code"),
    [
        ("bad", 400, "BAD_REQUEST"),
        ("unauth", 401, "UNAUTHORIZED"),
        ("forbidden", 403, "FORBIDDEN"),
        ("notfound", 404, "NOT_FOUND"),
        ("conflict", 409, "CONFLICT"),
        ("toolarge", 413, "PAYLOAD_TOO_LARGE"),
        ("unsupported", 415, "UNSUPPORTED_FILE"),
        ("llm", 503, "LLM_UNAVAILABLE"),
    ],
)
def test_app_error_subclasses_map_to_contract(probe_client: TestClient, name: str, status: int, code: str) -> None:
    err = assert_error_shape(probe_client.get(f"/_probe/app-error/{name}"), status, code)
    assert err["message"] == "Test mesajı: ğüşıöç İ"
    assert err["details"] == {"id": 7}


@pytest.mark.parametrize("name", list(_ERRORS))
def test_app_error_default_message_turkish(probe_client: TestClient, name: str) -> None:
    exc = _ERRORS[name]
    err = assert_error_shape(probe_client.get(f"/_probe/app-error-default/{name}"), exc.status_code, exc.code)
    assert err["message"] == exc.default_message
    assert err["details"] is None


# --------------------------------------------------------------------------------------------- get_current_user


def test_current_user_demo_when_auth_disabled(probe_client: TestClient) -> None:
    r = probe_client.get("/_probe/me")
    assert r.status_code == 200
    assert r.json()["id"] == 1
    assert r.json()["role"] == "ADMIN"


def test_current_user_demo_ignores_token_when_auth_disabled(probe_client: TestClient) -> None:
    r = probe_client.get("/_probe/me", headers={"Authorization": "Bearer herhangi-bir-sey"})
    assert r.status_code == 200
    assert r.json()["id"] == 1


def _auth_enabled_settings() -> Settings:
    return Settings(AUTH_ENABLED=True)


def test_current_user_401_when_auth_enabled_and_no_token(app: FastAPI) -> None:
    _add_probe_routes(app)
    app.dependency_overrides[get_settings] = _auth_enabled_settings
    with TestClient(app) as c:
        r = c.get("/_probe/me")
    err = assert_error_shape(r, 401, "UNAUTHORIZED")
    assert err["details"] is None


@pytest.mark.parametrize("header", ["Basic dXNlcjpwYXNz", "Bearer", "token-without-scheme"])
def test_current_user_401_when_auth_enabled_and_bad_header(app: FastAPI, header: str) -> None:
    _add_probe_routes(app)
    app.dependency_overrides[get_settings] = _auth_enabled_settings
    with TestClient(app) as c:
        r = c.get("/_probe/me", headers={"Authorization": header})
    assert_error_shape(r, 401, "UNAUTHORIZED")


def test_current_user_401_when_auth_enabled_and_token_unverified(app: FastAPI) -> None:
    # Token doğrulaması Taha bağlayana kadar yok: token olsa da 401 dönmeli (asla demo kullanıcı değil).
    _add_probe_routes(app)
    app.dependency_overrides[get_settings] = _auth_enabled_settings
    with TestClient(app) as c:
        r = c.get("/_probe/me", headers={"Authorization": "Bearer abc.def.ghi"})
    assert_error_shape(r, 401, "UNAUTHORIZED")


def test_auth_enabled_via_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AUTH_ENABLED", "true")
    get_settings.cache_clear()
    from main import create_app

    app = create_app()
    _add_probe_routes(app)
    with TestClient(app) as c:
        assert_error_shape(c.get("/_probe/me"), 401, "UNAUTHORIZED")
        # Sistem uçları auth istemez (sözleşme §0).
        assert c.get("/").status_code == 200
        assert c.get("/health").status_code == 200
        assert c.get("/api/v1/meta/enums").status_code == 200


# --------------------------------------------------------------------------------------------- CORS


def test_cors_preflight_allowed(client: TestClient) -> None:
    r = client.options(
        "/health",
        headers={"Origin": "http://localhost:8081", "Access-Control-Request-Method": "GET"},
    )
    assert r.status_code == 200
    assert r.headers.get("access-control-allow-origin") in ("*", "http://localhost:8081")


# --------------------------------------------------------------------------------------------- bağımsızlık


def test_create_app_returns_fresh_instances() -> None:
    from main import create_app

    a, b = create_app(), create_app()
    assert a is not b
