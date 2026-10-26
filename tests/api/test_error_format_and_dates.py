"""Genel kurallar (sözleşme §0): her uçta hata formatı tek tip; tüm tarih alanları ISO 8601 UTC."""

from typing import Any

import pytest
from fastapi.testclient import TestClient

from tests.api.helpers import assert_error_shape, assert_utc, pdf_upload

# (metot, yol, istek argümanları, beklenen status, beklenen code) — 20 ucun her biri en az bir kez
ERROR_CASES: list[tuple[str, str, dict[str, Any], int, str]] = [
    ("post", "/", {}, 405, "METHOD_NOT_ALLOWED"),
    ("delete", "/health", {}, 405, "METHOD_NOT_ALLOWED"),
    ("post", "/api/v1/meta/enums", {}, 405, "METHOD_NOT_ALLOWED"),
    ("post", "/auth/register", {"json": {"email": "x@y.com", "password": "kisa", "full_name": "X"}}, 422,
     "VALIDATION_ERROR"),
    ("post", "/auth/login", {"json": {"email": "demo@aerospace.local", "password": "yanlis"}}, 401, "UNAUTHORIZED"),
    ("post", "/auth/refresh", {"json": {"refresh_token": "sahte"}}, 401, "UNAUTHORIZED"),
    ("delete", "/auth/me", {}, 405, "METHOD_NOT_ALLOWED"),
    ("get", "/api/v1/standards", {"params": {"page_size": 101}}, 422, "VALIDATION_ERROR"),
    ("post", "/api/v1/standards", {"json": {"code": "do-178c", "title": "X", "standard_type": "CIVIL"}}, 409,
     "CONFLICT"),
    ("get", "/api/v1/standards/999", {}, 404, "NOT_FOUND"),
    ("post", "/api/v1/standards/999/document", {"files": pdf_upload(b"%PDF-1.4\n%%EOF\n")}, 404, "NOT_FOUND"),
    ("post", "/api/v1/standards/3/document", {"files": pdf_upload(b"duz metin")}, 415, "UNSUPPORTED_FILE"),
    ("get", "/api/v1/standards/999/index-status", {}, 404, "NOT_FOUND"),
    ("post", "/api/v1/search", {"json": {"query": "a"}}, 422, "VALIDATION_ERROR"),
    ("post", "/api/v1/chat/ask", {"json": {"question": "Soru nedir?", "conversation_id": 999}}, 404, "NOT_FOUND"),
    ("get", "/api/v1/chat/conversations", {"params": {"page": 0}}, 422, "VALIDATION_ERROR"),
    ("get", "/api/v1/chat/conversations/999", {}, 404, "NOT_FOUND"),
    ("post", "/api/v1/reports", {"files": pdf_upload(b"PK\x03\x04", "rapor.docx")}, 415, "UNSUPPORTED_FILE"),
    ("get", "/api/v1/reports", {"params": {"status": "COMPLETED"}}, 422, "VALIDATION_ERROR"),
    ("get", "/api/v1/reports/999", {}, 404, "NOT_FOUND"),
    ("post", "/api/v1/reports/999/analyses", {"json": {"query": "Uyumlu mu?"}}, 404, "NOT_FOUND"),
    ("put", "/api/v1/reports/1", {}, 405, "METHOD_NOT_ALLOWED"),
    ("get", "/api/v1/olmayan", {}, 404, "NOT_FOUND"),
]


@pytest.mark.parametrize(("method", "path", "kwargs", "status", "code"), ERROR_CASES,
                         ids=[f"{m.upper()} {p} -> {s}" for m, p, _, s, _ in ERROR_CASES])
def test_error_shape_everywhere(client: TestClient, method: str, path: str, kwargs: dict, status: int,
                                code: str) -> None:
    err = assert_error_shape(client.request(method, path, **kwargs), status, code)
    if status == 422:
        assert isinstance(err["details"], list) and err["details"]
        for d in err["details"]:
            assert set(d) == {"field", "message"}


def test_malformed_json_422(client: TestClient) -> None:
    r = client.post("/api/v1/search", content=b"{bozuk json", headers={"Content-Type": "application/json"})
    assert_error_shape(r, 422, "VALIDATION_ERROR")


def test_unexpected_error_500_hides_details(app, pdf_bytes: bytes) -> None:
    def boom(*_a, **_k):
        raise RuntimeError("gizli-ic-detay C:\\src\\x.py")

    with TestClient(app, raise_server_exceptions=False) as c:
        app.state.search.search = boom
        r = c.post("/api/v1/search", json={"query": "vibration"})
    err = assert_error_shape(r, 500, "INTERNAL_ERROR")
    assert "gizli" not in r.text and err["details"] is None


# --------------------------------------------------------------------------------------------- tarihler


def _collect_dates(obj: Any, out: list[tuple[str, Any]]) -> None:
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k.endswith("_at"):
                out.append((k, v))
            _collect_dates(v, out)
    elif isinstance(obj, list):
        for v in obj:
            _collect_dates(v, out)


def test_all_datetime_fields_are_utc(client: TestClient, pdf_bytes: bytes) -> None:
    responses = []
    responses.append(client.post("/auth/register", json={"email": "u@t.com", "password": "12345678",
                                                         "full_name": "U"}))
    responses.append(client.get("/auth/me"))
    new_std = client.post("/api/v1/standards", json={"code": "ISO-1", "title": "T", "standard_type": "INTL"})
    responses.append(new_std)
    responses.append(client.post("/api/v1/standards/3/document", files=pdf_upload(pdf_bytes)))
    responses.append(client.get("/api/v1/standards/3/index-status"))
    responses.append(client.get("/api/v1/standards"))
    responses.append(client.get("/api/v1/standards/1"))
    ask = client.post("/api/v1/chat/ask", json={"question": "Vibrasyon testi kaç saat?"})
    responses.append(ask)
    responses.append(client.get("/api/v1/chat/conversations"))
    responses.append(client.get(f"/api/v1/chat/conversations/{ask.json()['conversation_id']}"))
    rep = client.post("/api/v1/reports", files=pdf_upload(pdf_bytes))
    responses.append(rep)
    responses.append(client.get(f"/api/v1/reports/{rep.json()['id']}"))
    responses.append(client.get("/api/v1/reports"))
    responses.append(client.post("/api/v1/reports/1/analyses", json={"query": "Uyumlu mu?"}))

    dates: list[tuple[str, Any]] = []
    for r in responses:
        assert r.status_code < 300, (r.request.url, r.text)
        _collect_dates(r.json(), dates)
    non_null = [(k, v) for k, v in dates if v is not None]
    assert len(non_null) >= 20
    for key, value in non_null:
        try:
            assert_utc(value)
        except AssertionError as exc:  # pragma: no cover - mesajı netleştirir
            raise AssertionError(f"{key}={value!r} UTC değil") from exc
