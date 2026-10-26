"""Faz 2: Pydantic şemalarının sözleşmeye (docs/API_CONTRACT.md §0, §3 kutu, §4, §5, §6) uygunluğu.

Beklenen alan kümeleri sözleşmedeki JSON örneklerinden kopyalanmıştır; koddan türetilmez.
"""

import copy
import json
import re
from datetime import datetime, timedelta, timezone
from typing import Annotated, Any

import pytest
from fastapi import FastAPI, Query
from fastapi.testclient import TestClient
from pydantic import BaseModel, ValidationError

from src.application.schemas import common, search
from src.application.schemas.auth import LoginRequest, RefreshRequest, RegisterRequest, TokenResponse, UserOut
from src.application.schemas.chat import (
    ChatAnswerOut,
    ChatAskRequest,
    ConversationDetailOut,
    ConversationOut,
    MessageOut,
)
from src.application.schemas.common import ErrorDetail, ErrorResponse, PageParams
from src.application.schemas.meta import EnumsOut, Limits
from src.application.schemas.report import AnalysisCreate, AnalysisOut, ReportOut
from src.application.schemas.search import SearchRequest, SearchResponse, SourceOut
from src.application.schemas.standard import IndexStatusOut, StandardCreate, StandardOut
from src.domain import enums

CYRILLIC = re.compile("[" + chr(0x0400) + "-" + chr(0x052F) + "]")  # Kiril + Kiril Ek bloklari

# ---------------------------------------------------------------------------------------------------------------
# 1. Sözleşmeden kopyalanan alan kümeleri
# ---------------------------------------------------------------------------------------------------------------
CONTRACT_FIELDS: dict[type[BaseModel], set[str]] = {
    # §3 — "Bu hafta: Taha'nın şekli" kutusu (user / role YOK)
    RegisterRequest: {"email", "password", "full_name"},
    LoginRequest: {"email", "password"},
    RefreshRequest: {"refresh_token"},
    TokenResponse: {"access_token", "refresh_token", "token_type", "expires_in"},
    UserOut: {"id", "email", "full_name", "created_at"},
    # §4
    StandardOut: {
        "id", "code", "title", "standard_type", "version", "issuing_body", "publication_year", "description",
        "status", "index_status", "is_indexed", "has_document", "page_count", "chunk_count",
        "requirement_count", "indexed_at", "created_at", "updated_at",
    },
    StandardCreate: {"code", "title", "standard_type", "version", "issuing_body", "publication_year",
                     "description"},
    IndexStatusOut: {"standard_id", "index_status", "progress", "page_count", "chunk_count", "error_message",
                     "started_at", "finished_at"},
    # §5
    SourceOut: {"chunk_id", "standard_id", "standard_code", "requirement_id", "section", "page", "snippet",
                "score"},
    SearchRequest: {"query", "standard_ids", "top_k", "mode"},
    SearchResponse: {"query", "mode", "results", "duration_ms"},
    ChatAskRequest: {"question", "standard_ids", "conversation_id", "top_k"},
    ChatAnswerOut: {"conversation_id", "message_id", "question", "answer", "status", "sources", "model",
                    "duration_ms", "created_at"},
    ConversationOut: {"id", "title", "message_count", "standard_ids", "created_at", "updated_at"},
    ConversationDetailOut: {"id", "title", "message_count", "standard_ids", "created_at", "updated_at",
                            "messages"},
    MessageOut: {"id", "question", "answer", "status", "sources", "created_at"},
    # §6
    ReportOut: {"id", "title", "original_filename", "report_type", "status", "file_size_kb", "page_count",
                "analysis_count", "error_message", "uploaded_at", "processed_at"},
    AnalysisCreate: {"query", "standard_ids", "top_k"},
    AnalysisOut: {"id", "report_id", "query", "verdict", "verdict_label", "confidence", "is_high_confidence",
                  "reasoning", "sources", "model", "duration_ms", "created_at"},
    # §0 ortak
    ErrorResponse: {"error"},
    ErrorDetail: {"code", "message", "details"},
    PageParams: {"page", "page_size"},
    # §2 meta/enums
    EnumsOut: {"standard_types", "standard_statuses", "index_statuses", "requirement_categories", "report_types",
               "report_statuses", "verdicts", "search_modes", "limits"},
    Limits: {"max_upload_mb", "max_top_k", "max_page_size"},
}

MODELS = list(CONTRACT_FIELDS)
MODEL_IDS = [m.__name__ for m in MODELS]
# Örnek (examples) içermesi beklenen modeller (istek/cevap gövdeleri).
EXAMPLE_MODELS = [m for m in MODELS if m not in (ErrorDetail, EnumsOut, Limits)]


def _all_fields(model: type[BaseModel]) -> set[str]:
    return set(model.model_fields) | set(model.model_computed_fields)


def _examples(model: type[BaseModel]) -> list[dict[str, Any]]:
    extra = model.model_config.get("json_schema_extra") or {}
    assert isinstance(extra, dict), f"{model.__name__}: json_schema_extra dict değil"
    out = list(extra.get("examples") or [])
    if "example" in extra:
        out.append(extra["example"])
    return out


@pytest.mark.parametrize("model", MODELS, ids=MODEL_IDS)
def test_model_fields_match_contract(model: type[BaseModel]) -> None:
    assert _all_fields(model) == CONTRACT_FIELDS[model]


@pytest.mark.parametrize("model", MODELS, ids=MODEL_IDS)
def test_serialization_schema_properties_match_contract(model: type[BaseModel]) -> None:
    """Swagger'da görünen (serialization) şemanın alanları da sözleşmeyle birebir (computed alanlar dahil)."""
    props = set(model.model_json_schema(mode="serialization")["properties"])
    assert props == CONTRACT_FIELDS[model]


def test_standard_out_has_18_fields() -> None:
    assert len(_all_fields(StandardOut)) == 18


def test_taha_shape_has_no_user_or_role() -> None:
    assert "user" not in _all_fields(TokenResponse)
    assert "role" not in _all_fields(UserOut)


def test_conversation_detail_extends_conversation() -> None:
    assert issubclass(ConversationDetailOut, ConversationOut)
    msg = ConversationDetailOut.model_fields["messages"].annotation
    assert msg == list[MessageOut]


@pytest.mark.parametrize(("model", "field"), [
    (ChatAnswerOut, "sources"), (MessageOut, "sources"), (AnalysisOut, "sources"), (SearchResponse, "results"),
])
def test_sources_use_shared_source_out(model: type[BaseModel], field: str) -> None:
    assert model.model_fields[field].annotation == list[SourceOut]


# ---------------------------------------------------------------------------------------------------------------
# 2. Örnekler
# ---------------------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("model", EXAMPLE_MODELS, ids=[m.__name__ for m in EXAMPLE_MODELS])
def test_model_level_examples_exist_and_validate(model: type[BaseModel]) -> None:
    examples = _examples(model)
    assert examples, f"{model.__name__}: model düzeyinde örnek yok"
    for ex in examples:
        obj = model.model_validate(ex)
        # Örnek, modelin JSON çıktısıyla birebir aynı olmalı (eksik/fazla/yanlış biçimli anahtar yok).
        if model is not PageParams:
            assert set(ex) == CONTRACT_FIELDS[model], f"{model.__name__} örnek anahtarları sözleşmeden farklı"
        assert obj.model_dump(mode="json") == ex, f"{model.__name__} örneği round-trip'te değişti"


@pytest.mark.parametrize("model", MODELS, ids=MODEL_IDS)
def test_field_level_examples_validate(model: type[BaseModel]) -> None:
    """Her alanın `examples` değeri o alanın tipi ve sınırlarıyla geçerli (model örneğine yerleştirilerek)."""
    base_examples = _examples(model)
    if not base_examples:
        pytest.skip("model örneği yok (ayrı test kapsıyor)")
    base = base_examples[0]
    for name, info in model.model_fields.items():
        for value in info.examples or []:
            data = copy.deepcopy(base)
            data[name] = value
            try:
                model.model_validate(data)
            except ValidationError as e:  # pragma: no cover - mesaj için
                pytest.fail(f"{model.__name__}.{name} örneği geçersiz: {value!r}\n{e}")


@pytest.mark.parametrize("model", MODELS, ids=MODEL_IDS)
def test_every_field_has_example_in_openapi_schema(model: type[BaseModel]) -> None:
    schema = model.model_json_schema(mode="serialization")
    assert schema.get("examples") or schema.get("example") or all(
        ("examples" in p or "example" in p or "$ref" in p or "items" in p and "$ref" in p["items"])
        for p in schema["properties"].values()
    ), f"{model.__name__}: örneksiz alan var"


def _walk_strings(obj: Any) -> list[str]:
    if isinstance(obj, str):
        return [obj]
    if isinstance(obj, dict):
        return [s for k, v in obj.items() for s in _walk_strings(k) + _walk_strings(v)]
    if isinstance(obj, list | tuple):
        return [s for v in obj for s in _walk_strings(v)]
    return []


@pytest.mark.parametrize("model", MODELS, ids=MODEL_IDS)
def test_examples_have_no_cyrillic(model: type[BaseModel]) -> None:
    text = json.dumps(model.model_json_schema(mode="serialization"), ensure_ascii=False)
    text += json.dumps(model.model_json_schema(mode="validation"), ensure_ascii=False)
    found = CYRILLIC.findall(text)
    assert not found, f"{model.__name__}: Kiril karakter: {found}"


def test_examples_are_realistic() -> None:
    texts = " ".join(s for m in EXAMPLE_MODELS for s in _walk_strings(_examples(m)))
    assert "MIL-STD-810H" in texts
    assert "Method 514.8" in texts
    assert "Kağan Bayrak" in texts
    for placeholder in ("string", "lorem", "foo", "test123"):
        assert placeholder not in texts.lower().split(), placeholder


def test_example_enum_values_are_contract_values() -> None:
    std = _examples(StandardOut)[0]
    assert std["standard_type"] == "MIL" and std["status"] == "ACTIVE" and std["index_status"] == "INDEXED"
    assert _examples(IndexStatusOut)[0]["index_status"] in {e.value for e in enums.IndexStatus}
    assert _examples(SearchRequest)[0]["mode"] == "hybrid"
    assert _examples(SearchResponse)[0]["mode"] == "hybrid"
    assert _examples(ChatAnswerOut)[0]["status"] == "ANSWERED"
    rep = _examples(ReportOut)[0]
    assert rep["report_type"] == "TEST" and rep["status"] == "READY"
    an = _examples(AnalysisOut)[0]
    assert an["verdict"] == "PARTIAL" and an["verdict_label"] == "Kısmen Uyumlu"
    assert an["is_high_confidence"] is False and an["confidence"] == 0.78


CONTRACT_ENUMS: dict[type, list[str]] = {
    enums.StandardType: ["MIL", "CIVIL", "INTL"],
    enums.StandardStatus: ["ACTIVE", "SUPERSEDED", "ARCHIVED"],
    enums.IndexStatus: ["NOT_INDEXED", "PENDING", "PROCESSING", "INDEXED", "FAILED"],
    enums.RequirementCategory: ["ENVIRONMENTAL", "EMC", "SOFTWARE", "STRUCTURAL", "SAFETY"],
    enums.ReportType: ["DESIGN", "TEST", "QUAL", "COMPLIANCE"],
    enums.ReportStatus: ["UPLOADED", "PROCESSING", "READY", "FAILED"],
    enums.ComplianceVerdict: ["COMPLIANT", "PARTIAL", "NON_COMPLIANT", "INSUFFICIENT"],
    enums.SearchMode: ["semantic", "keyword", "hybrid"],
    enums.ChatStatus: ["ANSWERED", "NO_RESULTS", "LLM_UNAVAILABLE"],
    enums.UserRole: ["ENGINEER", "ADMIN"],
}


@pytest.mark.parametrize("enum_cls", list(CONTRACT_ENUMS), ids=[e.__name__ for e in CONTRACT_ENUMS])
def test_enum_values_match_contract(enum_cls: type) -> None:
    assert [e.value for e in enum_cls] == CONTRACT_ENUMS[enum_cls]


# ---------------------------------------------------------------------------------------------------------------
# 3. Sınırlar
# ---------------------------------------------------------------------------------------------------------------
def _ok(model: type[BaseModel], **data: Any) -> BaseModel:
    return model.model_validate(data)


def _bad(model: type[BaseModel], **data: Any) -> None:
    with pytest.raises(ValidationError):
        model.model_validate(data)


@pytest.mark.parametrize(("length", "valid"), [(2, False), (3, True), (2000, True), (2001, False)])
def test_chat_question_length(length: int, valid: bool) -> None:
    data = {"question": "a" * length}
    if valid:
        _ok(ChatAskRequest, **data)
    else:
        _bad(ChatAskRequest, **data)


def test_chat_question_required() -> None:
    _bad(ChatAskRequest)


def test_chat_conversation_id_null_and_int() -> None:
    assert _ok(ChatAskRequest, question="Vibrasyon?", conversation_id=None).conversation_id is None
    assert _ok(ChatAskRequest, question="Vibrasyon?").conversation_id is None
    assert _ok(ChatAskRequest, question="Vibrasyon?", conversation_id=5).conversation_id == 5
    _bad(ChatAskRequest, question="Vibrasyon?", conversation_id="abc")


TOP_K_MODELS = [
    (SearchRequest, {"query": "vibrasyon testi"}),
    (ChatAskRequest, {"question": "Vibrasyon testi kaç saat?"}),
    (AnalysisCreate, {"query": "Rapor uyumlu mu?"}),
]


@pytest.mark.parametrize(("model", "base"), TOP_K_MODELS, ids=[m.__name__ for m, _ in TOP_K_MODELS])
def test_top_k_bounds_and_default(model: type[BaseModel], base: dict[str, Any]) -> None:
    assert model.model_validate(base).top_k == 5
    for ok in (1, 20):
        assert model.model_validate({**base, "top_k": ok}).top_k == ok
    for bad in (0, 21, -1):
        _bad(model, **base, top_k=bad)


@pytest.mark.parametrize(("model", "base"), TOP_K_MODELS, ids=[m.__name__ for m, _ in TOP_K_MODELS])
def test_standard_ids_default_empty_and_int_list(model: type[BaseModel], base: dict[str, Any]) -> None:
    assert model.model_validate(base).standard_ids == []
    assert model.model_validate({**base, "standard_ids": [1, 2]}).standard_ids == [1, 2]
    _bad(model, **base, standard_ids=["x"])


def test_search_mode_default_and_invalid() -> None:
    assert _ok(SearchRequest, query="vibrasyon").mode == enums.SearchMode.HYBRID
    for m in ("semantic", "keyword", "hybrid"):
        assert _ok(SearchRequest, query="vibrasyon", mode=m).mode == m
    for bad in ("HYBRID", "fuzzy", ""):
        _bad(SearchRequest, query="vibrasyon", mode=bad)


def test_search_query_required() -> None:
    _bad(SearchRequest)
    _bad(SearchRequest, query="")


def test_analysis_query_required() -> None:
    _bad(AnalysisCreate)
    _bad(AnalysisCreate, query="")


@pytest.mark.parametrize(("pw", "valid"), [("a" * 7, False), ("a" * 8, True)])
def test_register_password_min_8(pw: str, valid: bool) -> None:
    data = {"email": "kagan@example.com", "password": pw, "full_name": "Kağan Bayrak"}
    if valid:
        _ok(RegisterRequest, **data)
    else:
        _bad(RegisterRequest, **data)


def test_register_invalid_email_and_missing_fields() -> None:
    _bad(RegisterRequest, email="kagan-at-example", password="min8karakter", full_name="Kağan")
    _bad(RegisterRequest, email="kagan@example.com", password="min8karakter")
    _bad(LoginRequest, email="kagan@example.com")
    _bad(RefreshRequest)
    _bad(RefreshRequest, refresh_token="")


def test_login_accepts_short_password() -> None:
    """Bilinçli karar: yanlış parola 422 değil 401 olsun diye login'de min 1."""
    _ok(LoginRequest, email="kagan@example.com", password="x")
    _bad(LoginRequest, email="kagan@example.com", password="")


def test_token_response_defaults() -> None:
    t = _ok(TokenResponse, access_token="a", refresh_token="r")
    assert t.token_type == "bearer" and t.expires_in == 3600  # access token 60 dk
    _bad(TokenResponse, access_token="a", refresh_token="r", token_type="mac")


def test_page_params_bounds_and_defaults() -> None:
    p = PageParams()
    assert (p.page, p.page_size) == (1, 20)
    assert PageParams(page=3, page_size=10).offset == 20
    for ok in (1, 100):
        assert PageParams(page_size=ok).page_size == ok
    for bad in (0, 101):
        _bad(PageParams, page_size=bad)
    _bad(PageParams, page=0)
    _bad(PageParams, page=-1)


def test_page_generic_shape() -> None:
    page = common.Page[SourceOut].model_validate(
        {"items": [_examples(SourceOut)[0]], "total": 42, "page": 1, "page_size": 20})
    assert set(page.model_dump()) == {"items", "total", "page", "page_size"}
    assert isinstance(page.items[0], SourceOut)


STD_CREATE_BASE = {"code": "MIL-STD-461G", "title": "EMI Control", "standard_type": "MIL"}


def test_standard_create_optional_fields_nullable() -> None:
    s = _ok(StandardCreate, **STD_CREATE_BASE, description=None, version=None, issuing_body=None,
            publication_year=None)
    assert s.description is None


@pytest.mark.parametrize(("field", "value"), [
    ("standard_type", "mil"), ("standard_type", "MILITARY"), ("code", ""), ("title", ""),
])
def test_standard_create_invalid(field: str, value: Any) -> None:
    _bad(StandardCreate, **{**STD_CREATE_BASE, field: value})


def test_standard_create_required() -> None:
    for key in STD_CREATE_BASE:
        _bad(StandardCreate, **{k: v for k, v in STD_CREATE_BASE.items() if k != key})


def _with(model: type[BaseModel], **override: Any) -> dict[str, Any]:
    return {**copy.deepcopy(_examples(model)[0]), **override}


@pytest.mark.parametrize(("model", "field", "bad"), [
    (StandardOut, "status", "active"), (StandardOut, "index_status", "DONE"),
    (IndexStatusOut, "index_status", "COMPLETED"), (ReportOut, "status", "COMPLETED"),
    (ReportOut, "report_type", "OTHER"), (AnalysisOut, "verdict", "UNKNOWN"),
    (ChatAnswerOut, "status", "OK"), (MessageOut, "status", "answered"),
])
def test_invalid_enum_values_rejected(model: type[BaseModel], field: str, bad: str) -> None:
    with pytest.raises(ValidationError):
        model.model_validate(_with(model, **{field: bad}))


@pytest.mark.parametrize(("model", "field"), [
    (AnalysisOut, "confidence"), (IndexStatusOut, "progress"), (SourceOut, "score"),
])
def test_unit_interval_fields(model: type[BaseModel], field: str) -> None:
    for ok in (0, 0.5, 1):
        model.model_validate(_with(model, **{field: ok}))
    for bad in (-0.01, 1.01):
        with pytest.raises(ValidationError):
            model.model_validate(_with(model, **{field: bad}))


@pytest.mark.parametrize(("model", "field"), [
    (ChatAnswerOut, "answer"), (MessageOut, "answer"), (IndexStatusOut, "error_message"),
    (IndexStatusOut, "finished_at"), (ReportOut, "error_message"), (StandardOut, "indexed_at"),
])
def test_contract_nullable_fields(model: type[BaseModel], field: str) -> None:
    obj = model.model_validate(_with(model, **{field: None}))
    assert obj.model_dump(mode="json")[field] is None


def test_chat_no_results_shape() -> None:
    """§5: NO_RESULTS → answer null, sources [] (yine 200)."""
    out = ChatAnswerOut.model_validate(_with(ChatAnswerOut, status="NO_RESULTS", answer=None, sources=[]))
    dumped = out.model_dump(mode="json")
    assert dumped["answer"] is None and dumped["sources"] == [] and dumped["status"] == "NO_RESULTS"


# ---------------------------------------------------------------------------------------------------------------
# 4. computed_field
# ---------------------------------------------------------------------------------------------------------------
@pytest.mark.parametrize(("verdict", "label"), [
    ("COMPLIANT", "Uyumlu"),
    ("PARTIAL", "Kısmen Uyumlu"),
    ("NON_COMPLIANT", "Uyumsuz"),
    ("INSUFFICIENT", "Yetersiz Bilgi"),
])
def test_verdict_label(verdict: str, label: str) -> None:
    a = AnalysisOut.model_validate(_with(AnalysisOut, verdict=verdict))
    assert a.verdict_label == label
    assert a.verdict_label == enums.ComplianceVerdict(verdict).label_tr
    assert not CYRILLIC.search(a.verdict_label)


def test_partial_label_uses_dotless_i() -> None:
    label = AnalysisOut.model_validate(_with(AnalysisOut, verdict="PARTIAL")).verdict_label
    assert label == "Kısmen Uyumlu"  # U+0131 LATIN SMALL LETTER DOTLESS I
    assert "i" not in label.split()[0]


def test_verdict_labels_match_meta_enums(client: TestClient) -> None:
    verdicts = client.get("/api/v1/meta/enums").json()["verdicts"]
    for v in verdicts:
        a = AnalysisOut.model_validate(_with(AnalysisOut, verdict=v["value"]))
        assert a.verdict_label == v["label_tr"]


@pytest.mark.parametrize(("confidence", "high"), [(0.0, False), (0.79, False), (0.7999, False), (0.8, True),
                                                  (0.95, True), (1.0, True)])
def test_is_high_confidence_threshold(confidence: float, high: bool) -> None:
    a = AnalysisOut.model_validate(_with(AnalysisOut, confidence=confidence))
    assert a.is_high_confidence is high


def test_computed_fields_in_json_dump() -> None:
    dumped = AnalysisOut.model_validate(_with(AnalysisOut, verdict="COMPLIANT", confidence=0.9)).model_dump(
        mode="json")
    assert dumped["verdict_label"] == "Uyumlu"
    assert dumped["is_high_confidence"] is True
    assert set(dumped) == CONTRACT_FIELDS[AnalysisOut]


def test_computed_fields_ignore_client_input() -> None:
    """Hesaplanan alanlar dışarıdan verilse bile veriden türetilir (veriyle çelişemez)."""
    a = AnalysisOut.model_validate(_with(AnalysisOut, verdict="COMPLIANT", confidence=0.1,
                                         verdict_label="Kısmen Uyumlu", is_high_confidence=True))
    assert a.verdict_label == "Uyumlu" and a.is_high_confidence is False


def test_computed_fields_in_serialization_schema() -> None:
    schema = AnalysisOut.model_json_schema(mode="serialization")
    assert schema["properties"]["verdict_label"]["type"] == "string"
    assert schema["properties"]["is_high_confidence"]["type"] == "boolean"
    assert {"verdict_label", "is_high_confidence"} <= set(schema.get("required", []))


# ---------------------------------------------------------------------------------------------------------------
# 5. Tarihler
# ---------------------------------------------------------------------------------------------------------------
DATETIME_FIELDS = [
    (UserOut, "created_at"), (StandardOut, "created_at"), (StandardOut, "updated_at"), (StandardOut, "indexed_at"),
    (IndexStatusOut, "started_at"), (ChatAnswerOut, "created_at"), (MessageOut, "created_at"),
    (ConversationOut, "created_at"), (ConversationOut, "updated_at"), (ReportOut, "uploaded_at"),
    (ReportOut, "processed_at"), (AnalysisOut, "created_at"),
]


@pytest.mark.parametrize(("model", "field"), DATETIME_FIELDS, ids=[f"{m.__name__}.{f}" for m, f in DATETIME_FIELDS])
def test_datetime_serialized_iso8601_utc(model: type[BaseModel], field: str) -> None:
    dt = datetime(2026, 10, 26, 9, 30, 0, tzinfo=timezone.utc)
    obj = model.model_validate(_with(model, **{field: dt}))
    raw = obj.model_dump(mode="json")[field]
    assert isinstance(raw, str)
    assert raw in ("2026-10-26T09:30:00Z", "2026-10-26T09:30:00+00:00"), raw
    parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    assert parsed == dt and parsed.utcoffset() == timedelta(0)
    # JSON (model_dump_json) yolu da aynı
    assert json.loads(obj.model_dump_json())[field] == raw


def test_datetime_example_string_parsed_as_utc() -> None:
    u = UserOut.model_validate(_examples(UserOut)[0])
    assert u.created_at.tzinfo is not None and u.created_at.utcoffset() == timedelta(0)


def test_datetime_offset_preserved() -> None:
    dt = datetime(2026, 10, 26, 12, 30, tzinfo=timezone(timedelta(hours=3)))
    raw = UserOut.model_validate(_with(UserOut, created_at=dt)).model_dump(mode="json")["created_at"]
    assert datetime.fromisoformat(raw) == dt and datetime.fromisoformat(raw).utcoffset() == timedelta(hours=3)


# ---------------------------------------------------------------------------------------------------------------
# 6. 422 Swagger düzeltmesi (geçici route ile)
# ---------------------------------------------------------------------------------------------------------------
@pytest.fixture
def probe_app(app: FastAPI) -> FastAPI:
    """create_app() + path param, body modeli ve PageParams sorgu modeli alan geçici bir route.

    openapi() önbelleğe aldığı için route, openapi() hiç çağrılmadan önce eklenir.
    """
    assert app.openapi_schema is None

    @app.post("/_probe/reports/{report_id}/analyses", response_model=AnalysisOut, status_code=201,
              summary="probe", tags=["Reports"])
    def _probe(report_id: int, body: AnalysisCreate,
               paging: Annotated[PageParams, Query()]) -> AnalysisOut:
        return AnalysisOut.model_validate(_with(AnalysisOut, report_id=report_id, query=body.query,
                                                duration_ms=paging.page_size))

    return app


PROBE_PATH = "/_probe/reports/{report_id}/analyses"


def test_probe_422_points_to_error_response(probe_app: FastAPI) -> None:
    spec = probe_app.openapi()
    op = spec["paths"][PROBE_PATH]["post"]
    assert "422" in op["responses"]
    schema = op["responses"]["422"]["content"]["application/json"]["schema"]
    assert schema == {"$ref": "#/components/schemas/ErrorResponse"}
    comps = spec["components"]["schemas"]
    assert "HTTPValidationError" not in comps
    assert "ValidationError" not in comps
    dumped = json.dumps(spec)
    assert "#/components/schemas/HTTPValidationError" not in dumped
    assert "#/components/schemas/ValidationError" not in dumped


def test_all_422_in_spec_point_to_error_response(probe_app: FastAPI) -> None:
    spec = probe_app.openapi()
    for path, item in spec["paths"].items():
        for method, op in item.items():
            resp = op.get("responses", {}).get("422") if isinstance(op, dict) else None
            if resp:
                assert resp["content"]["application/json"]["schema"]["$ref"].endswith("/ErrorResponse"), \
                    (method, path)


def test_probe_openapi_page_params_and_computed_fields(probe_app: FastAPI) -> None:
    spec = probe_app.openapi()
    op = spec["paths"][PROBE_PATH]["post"]
    params = {p["name"]: p for p in op["parameters"]}
    assert params["report_id"]["in"] == "path"
    assert params["page"]["in"] == "query" and params["page"]["schema"].get("minimum") == 1
    ps = params["page_size"]["schema"]
    assert params["page_size"]["in"] == "query"
    assert ps.get("minimum") == 1 and ps.get("maximum") == 100 and ps.get("default") == 20
    # 201 cevap şeması AnalysisOut ve hesaplanan alanları içeriyor
    ref = op["responses"]["201"]["content"]["application/json"]["schema"]["$ref"]
    out = spec["components"]["schemas"][ref.rsplit("/", 1)[-1]]
    assert {"verdict_label", "is_high_confidence"} <= set(out["properties"])
    assert set(out["properties"]) == CONTRACT_FIELDS[AnalysisOut]


def _assert_validation_error(r: Any, expected_field: str | None = None) -> list[dict[str, Any]]:
    assert r.status_code == 422, r.text
    body = r.json()
    assert set(body) == {"error"}
    assert set(body["error"]) == {"code", "message", "details"}
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert "Traceback" not in r.text
    details = body["error"]["details"]
    assert isinstance(details, list) and details
    if expected_field:
        assert expected_field in [d["field"] for d in details], details
    return details


def test_probe_runtime(probe_app: FastAPI) -> None:
    with TestClient(probe_app) as c:
        url = "/_probe/reports/3/analyses"
        ok = c.post(url, json={"query": "Rapor uyumlu mu?"})
        assert ok.status_code == 201, ok.text
        body = ok.json()
        assert body["report_id"] == 3 and body["duration_ms"] == 20  # page_size varsayılanı 20
        assert body["verdict_label"] == "Kısmen Uyumlu" and body["is_high_confidence"] is False
        assert c.post(url + "?page=2&page_size=100", json={"query": "abc"}).status_code == 201

        _assert_validation_error(c.post(url + "?page_size=101", json={"query": "abc"}), "query.page_size")
        _assert_validation_error(c.post(url + "?page_size=0", json={"query": "abc"}), "query.page_size")
        _assert_validation_error(c.post(url + "?page=0", json={"query": "abc"}), "query.page")
        _assert_validation_error(c.post("/_probe/reports/abc/analyses", json={"query": "abc"}), "path.report_id")
        _assert_validation_error(c.post(url, json={"query": "abc", "top_k": 21}), "body.top_k")
        _assert_validation_error(c.post(url, json={}), "body.query")


# ---------------------------------------------------------------------------------------------------------------
# 7. Sabit tutarlılığı
# ---------------------------------------------------------------------------------------------------------------
def test_constants_match_meta_limits(client: TestClient) -> None:
    limits = client.get("/api/v1/meta/enums").json()["limits"]
    assert search.MAX_TOP_K == limits["max_top_k"] == 20
    assert search.DEFAULT_TOP_K == 5
    assert common.MAX_PAGE_SIZE == limits["max_page_size"] == 100
    assert common.DEFAULT_PAGE_SIZE == 20


def test_schema_bounds_use_constants() -> None:
    sr = SearchRequest.model_json_schema()["properties"]["top_k"]
    assert sr["maximum"] == search.MAX_TOP_K and sr["default"] == search.DEFAULT_TOP_K
    pp = PageParams.model_json_schema()["properties"]["page_size"]
    assert pp["maximum"] == common.MAX_PAGE_SIZE
