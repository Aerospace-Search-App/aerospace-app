"""Faz 4: sözleşme kapsama testi — `docs/TASK_API_SKELETON.md` "Çekirdek endpoint seti (20)" tablosu ↔ kod birebir.

Beklenen liste aşağıda SABİT yazılıdır (tablodan kopyalandı); koddan türetilmez. Tablo değişirse önce doküman,
sonra bu liste güncellenir.
"""

from typing import Any

import pytest
from fastapi.testclient import TestClient

from tests.api.test_openapi import _has_example, _resolve

# (metot, yol, başarı kodu, tag) — TASK_API_SKELETON.md tablosu #1–#20
CORE_ENDPOINTS: list[tuple[str, str, int, str]] = [
    ("get", "/", 200, "System"),
    ("get", "/health", 200, "System"),
    ("get", "/api/v1/meta/enums", 200, "System"),
    ("post", "/auth/register", 201, "Auth"),
    ("post", "/auth/login", 200, "Auth"),
    ("post", "/auth/refresh", 200, "Auth"),
    ("get", "/auth/me", 200, "Auth"),
    ("get", "/api/v1/standards", 200, "Standards"),
    ("post", "/api/v1/standards", 201, "Standards"),
    ("get", "/api/v1/standards/{standard_id}", 200, "Standards"),
    ("post", "/api/v1/standards/{standard_id}/document", 202, "Standards"),
    ("get", "/api/v1/standards/{standard_id}/index-status", 200, "Standards"),
    ("post", "/api/v1/search", 200, "Search & Chat"),
    ("post", "/api/v1/chat/ask", 200, "Search & Chat"),
    ("get", "/api/v1/chat/conversations", 200, "Search & Chat"),
    ("get", "/api/v1/chat/conversations/{conversation_id}", 200, "Search & Chat"),
    ("post", "/api/v1/reports", 202, "Reports"),
    ("get", "/api/v1/reports", 200, "Reports"),
    ("get", "/api/v1/reports/{report_id}", 200, "Reports"),
    ("post", "/api/v1/reports/{report_id}/analyses", 201, "Reports"),
]

# Sözleşme §0: auth istemeyen uçlar. Geri kalan hepsi HTTPBearer ile kilitli.
PUBLIC = {("get", "/"), ("get", "/health"), ("get", "/api/v1/meta/enums"),
          ("post", "/auth/register"), ("post", "/auth/login"), ("post", "/auth/refresh")}

# Sözleşme §3–§6 "Hatalar" sütunları: Swagger'da en az bu hata kodları belgelenmiş olmalı.
REQUIRED_ERRORS: dict[tuple[str, str], set[str]] = {
    ("post", "/auth/register"): {"409", "422"},
    ("post", "/auth/login"): {"401"},
    ("post", "/auth/refresh"): {"401"},
    ("get", "/auth/me"): {"401"},
    ("get", "/api/v1/standards"): {"422"},
    ("post", "/api/v1/standards"): {"403", "409", "422"},
    ("get", "/api/v1/standards/{standard_id}"): {"404"},
    ("post", "/api/v1/standards/{standard_id}/document"): {"403", "404", "409", "413", "415"},
    ("get", "/api/v1/standards/{standard_id}/index-status"): {"404"},
    ("post", "/api/v1/search"): {"422"},
    ("post", "/api/v1/chat/ask"): {"404", "422"},
    ("get", "/api/v1/chat/conversations/{conversation_id}"): {"404"},
    ("post", "/api/v1/reports"): {"413", "415", "422"},
    ("get", "/api/v1/reports"): {"422"},
    ("get", "/api/v1/reports/{report_id}"): {"404"},
    ("post", "/api/v1/reports/{report_id}/analyses"): {"404", "409", "503", "422"},
}

HTTP_METHODS = {"get", "post", "put", "patch", "delete", "head", "options", "trace"}
IDS = [f"{m.upper()} {p}" for m, p, _, _ in CORE_ENDPOINTS]


@pytest.fixture
def spec(client: TestClient) -> dict[str, Any]:
    r = client.get("/openapi.json")
    assert r.status_code == 200
    return r.json()


def _ops(spec: dict[str, Any]) -> set[tuple[str, str]]:
    return {(m, p) for p, item in spec["paths"].items() for m in item if m in HTTP_METHODS}


# --------------------------------------------------------------------------------------------- kapsama


def test_core_table_has_20_unique_pairs() -> None:
    pairs = {(m, p) for m, p, _, _ in CORE_ENDPOINTS}
    assert len(CORE_ENDPOINTS) == 20 and len(pairs) == 20


def test_all_20_core_endpoints_present_and_nothing_extra(spec: dict[str, Any]) -> None:
    expected = {(m, p) for m, p, _, _ in CORE_ENDPOINTS}
    actual = _ops(spec)
    missing = sorted(expected - actual)
    extra = sorted(actual - expected)
    assert not missing, f"eksik endpoint: {missing}"
    assert not extra, f"fazla endpoint: {extra}"


def test_app_openapi_matches_served_json(client: TestClient, spec: dict[str, Any]) -> None:
    assert _ops(client.app.openapi()) == _ops(spec)


@pytest.mark.parametrize(("method", "path", "status", "tag"), CORE_ENDPOINTS, ids=IDS)
def test_success_status_and_tag(spec: dict[str, Any], method: str, path: str, status: int, tag: str) -> None:
    op = spec["paths"][path][method]
    success = {c for c in op["responses"] if c.startswith("2")}
    assert success == {str(status)}, f"{method.upper()} {path}: 2xx {success}, beklenen {status}"
    assert op.get("tags") == [tag]


# --------------------------------------------------------------------------------------------- Swagger kalitesi


@pytest.mark.parametrize(("method", "path", "status", "tag"), CORE_ENDPOINTS, ids=IDS)
def test_operation_documentation(spec: dict[str, Any], method: str, path: str, status: int, tag: str) -> None:
    op = spec["paths"][path][method]
    assert op.get("summary", "").strip(), "summary yok"
    assert op.get("description", "").strip(), "description yok"
    ok = op["responses"][str(status)]
    schema = ok["content"]["application/json"]["schema"]
    assert "$ref" in schema, f"2xx şeması $ref değil: {schema}"
    assert _has_example(spec, schema), "2xx cevap şemasında örnek değer yok"


@pytest.mark.parametrize(("method", "path", "status", "tag"), CORE_ENDPOINTS, ids=IDS)
def test_error_responses_use_error_response(spec: dict[str, Any], method: str, path: str, status: int,
                                            tag: str) -> None:
    op = spec["paths"][path][method]
    err_codes = [c for c in op["responses"] if c[0] in "45"]
    assert err_codes, "hata cevabı belgelenmemiş"
    for c in err_codes:
        ref = op["responses"][c]["content"]["application/json"]["schema"].get("$ref", "")
        assert ref.endswith("/ErrorResponse"), (c, ref)
    has_input = bool(op.get("parameters")) or "requestBody" in op
    if has_input:
        assert "422" in op["responses"], "girdi alan uçta 422 belgelenmemiş"
    required = REQUIRED_ERRORS.get((method, path), set())
    assert required <= set(op["responses"]), f"eksik hata kodu: {sorted(required - set(op['responses']))}"


def test_no_fastapi_validation_schema_left(spec: dict[str, Any]) -> None:
    assert "HTTPValidationError" not in spec["components"]["schemas"]


@pytest.mark.parametrize(("method", "path", "status", "tag"), CORE_ENDPOINTS, ids=IDS)
def test_security_matches_contract(spec: dict[str, Any], method: str, path: str, status: int, tag: str) -> None:
    op = spec["paths"][path][method]
    if (method, path) in PUBLIC:
        assert not op.get("security"), "auth istemeyen uçta security var"
    else:
        assert {"HTTPBearer": []} in (op.get("security") or []), "kilitli uçta HTTPBearer yok"
        assert "401" in op["responses"], "kilitli uçta 401 belgelenmemiş"


@pytest.mark.parametrize(("method", "path", "status", "tag"), CORE_ENDPOINTS, ids=IDS)
def test_request_body_documented_with_example(spec: dict[str, Any], method: str, path: str, status: int,
                                              tag: str) -> None:
    op = spec["paths"][path][method]
    body = op.get("requestBody")
    if body is None:
        assert method == "get", "POST ucunda requestBody yok"
        return
    content = body["content"]
    if "application/json" in content:
        schema = content["application/json"]["schema"]
        assert "$ref" in schema
        resolved = _resolve(spec, schema["$ref"])
        assert resolved.get("examples") or resolved.get("example") or _has_example(spec, schema), \
            "JSON istek gövdesinde örnek yok"
    else:
        assert "multipart/form-data" in content, content
        resolved = _resolve(spec, content["multipart/form-data"]["schema"]["$ref"])
        file_prop = resolved["properties"]["file"]
        assert file_prop.get("format") == "binary" or file_prop.get("contentMediaType"), file_prop
        assert "file" in resolved.get("required", [])


@pytest.mark.parametrize("path", ["/api/v1/standards", "/api/v1/chat/conversations", "/api/v1/reports"])
def test_list_endpoints_are_paged(spec: dict[str, Any], path: str) -> None:
    op = spec["paths"][path]["get"]
    params = {p["name"]: p for p in op["parameters"]}
    assert params["page"]["schema"]["minimum"] == 1
    assert params["page_size"]["schema"]["maximum"] == 100
    ref = op["responses"]["200"]["content"]["application/json"]["schema"]["$ref"]
    page_schema = _resolve(spec, ref)
    assert set(page_schema["properties"]) == {"items", "total", "page", "page_size"}
    assert "$ref" in page_schema["properties"]["items"]["items"]
