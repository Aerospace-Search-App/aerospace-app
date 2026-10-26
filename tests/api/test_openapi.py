"""Faz 1: Swagger / OpenAPI kalitesi (sözleşme §0, CLAUDE.md "API kuralları")."""

from typing import Any

import pytest
from fastapi.testclient import TestClient

FAZ1_OPERATIONS = [("get", "/"), ("get", "/health"), ("get", "/api/v1/meta/enums")]
HTTP_METHODS = {"get", "post", "put", "patch", "delete", "head", "options", "trace"}


@pytest.fixture
def spec(client: TestClient) -> dict[str, Any]:
    r = client.get("/openapi.json")
    assert r.status_code == 200
    return r.json()


def _resolve(spec: dict[str, Any], ref: str) -> dict[str, Any]:
    assert ref.startswith("#/components/schemas/"), ref
    return spec["components"]["schemas"][ref.rsplit("/", 1)[-1]]


def _has_example(spec: dict[str, Any], schema: dict[str, Any], seen: set[str] | None = None) -> bool:
    """Şemanın kendisinde ya da tüm (iç içe) alanlarında örnek değer var mı."""
    seen = seen if seen is not None else set()
    if "$ref" in schema:
        name = schema["$ref"]
        if name in seen:
            return True
        seen.add(name)
        return _has_example(spec, _resolve(spec, name), seen)
    if "example" in schema or "examples" in schema:
        return True
    props = schema.get("properties")
    if props:
        return all(_has_example(spec, p, seen) for p in props.values())
    for key in ("allOf", "anyOf", "oneOf"):
        if key in schema:
            return any(_has_example(spec, s, seen) for s in schema[key])
    return False


def test_openapi_info(spec: dict[str, Any]) -> None:
    info = spec["info"]
    assert "Mobil API" in info["title"]
    assert info["version"] == "1.1.0"
    desc = info.get("description", "")
    assert len(desc.strip()) > 100
    assert any(ch in desc for ch in "ğşıİöüç")
    assert '"error"' in desc
    assert "page_size" in desc


def test_openapi_security_scheme_http_bearer(spec: dict[str, Any]) -> None:
    schemes = spec["components"]["securitySchemes"]
    assert "HTTPBearer" in schemes
    assert schemes["HTTPBearer"]["type"] == "http"
    assert schemes["HTTPBearer"]["scheme"].lower() == "bearer"
    assert len(schemes) == 1  # çift kayıt yok


def test_openapi_tags_described(spec: dict[str, Any]) -> None:
    tags = {t["name"]: t.get("description", "") for t in spec.get("tags", [])}
    for name in ("System", "Auth", "Standards", "Search & Chat", "Reports"):
        assert name in tags, f"tag eksik: {name}"
        assert tags[name].strip(), f"tag açıklaması boş: {name}"


# Not: Faz 1'deki "sadece 3 uç var" testi kaldırıldı; tam liste kontrolü artık
# tests/api/test_contract_coverage.py'de (20 uç, eksik/fazla yok).


@pytest.mark.parametrize(("method", "path"), FAZ1_OPERATIONS)
def test_operation_quality(spec: dict[str, Any], method: str, path: str) -> None:
    op = spec["paths"][path][method]
    assert op.get("summary", "").strip()
    assert op.get("description", "").strip()
    assert op.get("tags") == ["System"]
    ok = op["responses"]["200"]
    schema = ok["content"]["application/json"]["schema"]
    assert "$ref" in schema, schema
    assert _has_example(spec, schema), f"{method.upper()} {path}: cevap şemasında örnek değer yok"
    # Hata cevabı da belgelenmiş ve ErrorResponse'u gösteriyor.
    err_codes = [c for c in op["responses"] if c[0] in "45"]
    assert err_codes, "hata cevabı belgelenmemiş"
    for c in err_codes:
        ref = op["responses"][c]["content"]["application/json"]["schema"].get("$ref", "")
        assert ref.endswith("/ErrorResponse"), (c, ref)
    # Sistem uçları auth istemez (sözleşme §0).
    assert not op.get("security")


def test_error_response_schema_has_example(spec: dict[str, Any]) -> None:
    schemas = spec["components"]["schemas"]
    assert "ErrorResponse" in schemas
    er = schemas["ErrorResponse"]
    assert er.get("example") or er.get("examples")
    assert _has_example(spec, {"$ref": "#/components/schemas/ErrorDetail"})
    assert set(schemas["ErrorDetail"]["properties"]) == {"code", "message", "details"}


def test_docs_page(client: TestClient) -> None:
    r = client.get("/docs")
    assert r.status_code == 200
    assert "swagger-ui" in r.text.lower()


def test_openapi_json_utf8_turkish(client: TestClient) -> None:
    r = client.get("/openapi.json")
    assert "Sağlık kontrolü".encode("utf-8") in r.content
