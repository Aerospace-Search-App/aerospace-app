"""Rapor ve analiz uçları (sözleşme §6): yükleme (202 → READY), liste/filtre, detay, analiz (201/404/409/503)."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.domain.enums import ReportStatus
from tests.api.helpers import (
    ANALYSIS_KEYS,
    OTHER_ADMIN,
    PAGE_KEYS,
    REPORT_KEYS,
    UUID_PDF_NAME,
    act_as,
    assert_error_shape,
    assert_source,
    assert_utc,
    pdf_upload,
    stored_files,
)

BASE = "/api/v1/reports"
QUERY = "Rapor vibrasyon gereksinimlerini karşılıyor mu?"


def _upload(c: TestClient, content: bytes, filename: str = "rapor.pdf", **form) -> dict:
    r = c.post(BASE, files=pdf_upload(content, filename), data=form)
    assert r.status_code == 202, r.text
    return r.json()


def _analyze(c: TestClient, report_id: int = 1, **body):
    return c.post(f"{BASE}/{report_id}/analyses", json={"query": QUERY, "standard_ids": [1], **body})


# ============================================================================================= seed + GET /reports


def test_seed_ready_report(client: TestClient) -> None:
    body = client.get(BASE).json()
    assert set(body) == PAGE_KEYS
    assert body["total"] == 1 and body["page"] == 1 and body["page_size"] == 20
    rep = body["items"][0]
    assert set(rep) == REPORT_KEYS
    assert rep["title"] == "Telsiz Titreşim Test Raporu"
    assert rep["status"] == "READY" and rep["report_type"] == "TEST"
    assert rep["analysis_count"] == 0 and rep["error_message"] is None
    assert_utc(rep["uploaded_at"])
    assert_utc(rep["processed_at"])


# ============================================================================================= POST /reports


def test_upload_202_uploaded_then_ready(client: TestClient, pdf_bytes: bytes) -> None:
    body = _upload(client, pdf_bytes, "telsiz_rapor.pdf", title="Telsiz Şok Test Raporu", report_type="TEST")
    assert set(body) == REPORT_KEYS
    assert body["status"] in ("UPLOADED", "PROCESSING")
    assert body["title"] == "Telsiz Şok Test Raporu"
    assert body["original_filename"] == "telsiz_rapor.pdf"
    assert body["report_type"] == "TEST"
    assert body["analysis_count"] == 0
    assert body["processed_at"] is None and body["page_count"] is None and body["error_message"] is None
    assert body["file_size_kb"] == round(len(pdf_bytes) / 1024, 1)
    assert_utc(body["uploaded_at"])

    r = client.get(f"{BASE}/{body['id']}")
    assert r.status_code == 200
    done = r.json()
    assert done["status"] == "READY"
    assert_utc(done["processed_at"])
    assert done["page_count"] is not None and done["page_count"] >= 1
    assert done["error_message"] is None


def test_upload_defaults_title_and_type(client: TestClient, pdf_bytes: bytes) -> None:
    body = _upload(client, pdf_bytes, "telsiz_titresim-raporu.pdf")
    assert body["report_type"] == "DESIGN"
    assert body["title"].strip()
    assert "telsiz" in body["title"].lower() and ".pdf" not in body["title"]


def test_upload_blank_title_derived(client: TestClient, pdf_bytes: bytes) -> None:
    body = _upload(client, pdf_bytes, "kalite_raporu.pdf", title="   ")
    assert body["title"].strip() and "kalite" in body["title"].lower()


def test_upload_original_filename_strips_path(client: TestClient, pdf_bytes: bytes, storage_dir) -> None:
    body = _upload(client, pdf_bytes, "C:\\Users\\x\\gizli\\rapor.pdf")
    assert body["original_filename"] == "rapor.pdf"
    files = stored_files(storage_dir)
    assert len(files) == 1 and UUID_PDF_NAME.match(files[0].name)
    assert files[0].parent == storage_dir


def test_upload_fake_pdf_415(client: TestClient, fake_pdf, storage_dir) -> None:
    assert_error_shape(client.post(BASE, files={"file": fake_pdf}), 415, "UNSUPPORTED_FILE")
    assert stored_files(storage_dir) == []
    assert client.get(BASE).json()["total"] == 1  # kayıt oluşmadı


def test_upload_docx_415(client: TestClient, pdf_bytes: bytes, storage_dir) -> None:
    r = client.post(BASE, files=pdf_upload(pdf_bytes, "rapor.docx",
                                           "application/vnd.openxmlformats-officedocument.wordprocessingml.document"))
    assert_error_shape(r, 415, "UNSUPPORTED_FILE")
    assert stored_files(storage_dir) == []


def test_upload_too_large_413(make_client, storage_dir) -> None:
    c = make_client(MAX_UPLOAD_MB="1")
    big = b"%PDF-1.4\n" + b"0" * (1024 * 1024 + 10)
    assert_error_shape(c.post(BASE, files=pdf_upload(big)), 413, "PAYLOAD_TOO_LARGE")
    assert stored_files(storage_dir) == []
    assert c.get(BASE).json()["total"] == 1


@pytest.mark.parametrize("data", [{"report_type": "MEMO"}, {"title": "x" * 201}])
def test_upload_invalid_form_422(client: TestClient, pdf_bytes: bytes, data: dict, storage_dir) -> None:
    assert_error_shape(client.post(BASE, files=pdf_upload(pdf_bytes), data=data), 422, "VALIDATION_ERROR")
    assert stored_files(storage_dir) == []


def test_upload_missing_file_422(client: TestClient) -> None:
    assert_error_shape(client.post(BASE, data={"title": "Dosyasız"}), 422, "VALIDATION_ERROR")


def test_upload_processing_failure_recorded(app: FastAPI, client: TestClient, pdf_bytes: bytes) -> None:
    def boom(_path: str) -> int:
        raise RuntimeError("iç hata C:\\gizli")

    app.state.storage.count_pages = boom
    body = _upload(client, pdf_bytes)
    rep = client.get(f"{BASE}/{body['id']}").json()
    assert rep["status"] == "FAILED"
    assert rep["error_message"] and "gizli" not in rep["error_message"]


# ============================================================================================= liste filtreleri


def test_list_newest_first_and_filters(client: TestClient, pdf_bytes: bytes) -> None:
    new = _upload(client, pdf_bytes, "kalite.pdf", title="Kalite Raporu")  # DESIGN, işlendi → READY
    body = client.get(BASE).json()
    assert body["total"] == 2
    assert [r["id"] for r in body["items"]] == [new["id"], 1]

    def ids(**params) -> list[int]:
        res = client.get(BASE, params=params)
        assert res.status_code == 200, res.text
        return [r["id"] for r in res.json()["items"]]

    assert ids(report_type="TEST") == [1]
    assert ids(report_type="DESIGN") == [new["id"]]
    assert ids(report_type="QUAL") == []
    assert ids(status="READY") == [new["id"], 1]
    assert ids(status="FAILED") == []
    assert ids(q="titreşim") == [1]
    assert ids(q="kalite") == [new["id"]]
    assert ids(q="telsiz_titresim") == [1]  # dosya adında arama
    assert ids(q="yok") == []
    page = client.get(BASE, params={"page": 2, "page_size": 1}).json()
    assert page["total"] == 2 and page["page"] == 2 and [r["id"] for r in page["items"]] == [1]


def test_list_status_uploaded_filter(app: FastAPI, client: TestClient) -> None:
    app.state.report_repo.get(1).status = ReportStatus.UPLOADED
    assert client.get(BASE, params={"status": "UPLOADED"}).json()["total"] == 1
    assert client.get(BASE, params={"status": "READY"}).json()["total"] == 0


@pytest.mark.parametrize("params", [{"status": "DONE"}, {"report_type": "test"}, {"page_size": 101}, {"page": 0}])
def test_list_invalid_query_422(client: TestClient, params: dict) -> None:
    assert_error_shape(client.get(BASE, params=params), 422, "VALIDATION_ERROR")


def test_list_only_own_reports(app: FastAPI, client: TestClient, pdf_bytes: bytes) -> None:
    act_as(app, OTHER_ADMIN)
    assert client.get(BASE).json()["total"] == 0
    other = _upload(client, pdf_bytes, "baskasinin.pdf")
    assert client.get(BASE).json()["total"] == 1
    app.dependency_overrides.clear()
    demo_ids = [r["id"] for r in client.get(BASE).json()["items"]]
    assert demo_ids == [1] and other["id"] not in demo_ids
    assert_error_shape(client.get(f"{BASE}/{other['id']}"), 404, "NOT_FOUND")


# ============================================================================================= GET /reports/{id}


def test_get_report_200(client: TestClient) -> None:
    r = client.get(f"{BASE}/1")
    assert r.status_code == 200
    body = r.json()
    assert set(body) == REPORT_KEYS
    assert body["id"] == 1 and body["page_count"] == 24 and body["file_size_kb"] == 812.4


def test_get_report_404(client: TestClient) -> None:
    assert_error_shape(client.get(f"{BASE}/999"), 404, "NOT_FOUND")


def test_get_report_non_int_422(client: TestClient) -> None:
    assert_error_shape(client.get(f"{BASE}/abc"), 422, "VALIDATION_ERROR")


def test_get_other_users_report_404(app: FastAPI, client: TestClient) -> None:
    act_as(app, OTHER_ADMIN)
    assert_error_shape(client.get(f"{BASE}/1"), 404, "NOT_FOUND")


# ============================================================================================= POST /reports/{id}/analyses


def test_analysis_201(client: TestClient) -> None:
    r = _analyze(client)
    assert r.status_code == 201, r.text
    body = r.json()
    assert set(body) == ANALYSIS_KEYS
    assert body["report_id"] == 1 and body["query"] == QUERY
    assert body["verdict"] == "INSUFFICIENT"
    assert body["verdict_label"] == "Yetersiz Bilgi"
    assert body["confidence"] == 0.5
    assert body["is_high_confidence"] is False
    assert body["reasoning"].startswith("[DEMO]")
    assert body["model"] == "mock-llm"
    assert body["duration_ms"] >= 0
    assert body["sources"]
    for src in body["sources"]:
        assert_source(src)
        assert src["standard_id"] == 1
    assert_utc(body["created_at"])


def test_analysis_increments_count(client: TestClient) -> None:
    first = _analyze(client).json()
    assert client.get(f"{BASE}/1").json()["analysis_count"] == 1
    second = _analyze(client).json()
    assert second["id"] != first["id"]
    assert client.get(f"{BASE}/1").json()["analysis_count"] == 2


def test_analysis_top_k_and_all_standards(client: TestClient) -> None:
    body = client.post(f"{BASE}/1/analyses", json={"query": QUERY, "top_k": 20}).json()
    assert {s["standard_id"] for s in body["sources"]} == {1, 2}
    assert len(_analyze(client, top_k=2).json()["sources"]) == 2


def test_flow_upload_ready_then_analyze(client: TestClient, pdf_bytes: bytes) -> None:
    rep = _upload(client, pdf_bytes, "yeni_rapor.pdf", report_type="QUAL")
    assert client.get(f"{BASE}/{rep['id']}").json()["status"] == "READY"
    r = _analyze(client, rep["id"])
    assert r.status_code == 201
    assert r.json()["report_id"] == rep["id"]
    assert client.get(f"{BASE}/{rep['id']}").json()["analysis_count"] == 1


def test_analysis_unknown_report_404(client: TestClient) -> None:
    assert_error_shape(_analyze(client, 999), 404, "NOT_FOUND")


def test_analysis_other_users_report_404(app: FastAPI, client: TestClient) -> None:
    act_as(app, OTHER_ADMIN)
    assert_error_shape(_analyze(client, 1), 404, "NOT_FOUND")
    app.dependency_overrides.clear()
    assert client.get(f"{BASE}/1").json()["analysis_count"] == 0


@pytest.mark.parametrize("status", [ReportStatus.UPLOADED, ReportStatus.PROCESSING, ReportStatus.FAILED])
def test_analysis_report_not_ready_409(app: FastAPI, client: TestClient, status: ReportStatus) -> None:
    app.state.report_repo.get(1).status = status
    assert_error_shape(_analyze(client), 409, "CONFLICT")
    assert app.state.report_repo.get(1).analysis_count == 0
    assert app.state.analysis_repo.get(1) is None


def test_analysis_llm_unavailable_503_not_saved(make_client) -> None:
    c = make_client(LLM_PROVIDER="gemini")
    err = assert_error_shape(_analyze(c), 503, "LLM_UNAVAILABLE")
    assert err["details"] is None
    assert c.get(f"{BASE}/1").json()["analysis_count"] == 0
    assert c.app.state.analysis_repo.get(1) is None


@pytest.mark.parametrize("payload", [
    {"query": "ab"}, {"query": "x" * 2001}, {}, {"query": QUERY, "top_k": 0}, {"query": QUERY, "top_k": 21},
    {"query": QUERY, "standard_ids": "1"},
])
def test_analysis_invalid_body_422(client: TestClient, payload: dict) -> None:
    assert_error_shape(client.post(f"{BASE}/1/analyses", json=payload), 422, "VALIDATION_ERROR")


def test_analysis_query_boundaries(client: TestClient) -> None:
    assert client.post(f"{BASE}/1/analyses", json={"query": "abc"}).status_code == 201
    assert client.post(f"{BASE}/1/analyses", json={"query": "q" * 2000}).status_code == 201


# ============================================================================================= Türkçe büyük/küçük harf araması


@pytest.mark.parametrize("q", ["TİTREŞİM", "titreşim", "Titreşim", "TITREŞIM", "titresim", "TELSİZ TİTREŞİM"])
def test_list_q_turkish_case_insensitive(client: TestClient, q: str) -> None:
    body = client.get(BASE, params={"q": q}).json()
    assert [r["id"] for r in body["items"]] == [1], q
    assert body["total"] == 1


def test_list_q_turkish_no_false_match(client: TestClient) -> None:
    assert client.get(BASE, params={"q": "şok"}).json()["total"] == 0


@pytest.mark.parametrize("query", ["   ", " ab "])
def test_analysis_whitespace_only_query_422(client: TestClient, query: str) -> None:
    assert_error_shape(client.post(f"{BASE}/1/analyses", json={"query": query}), 422, "VALIDATION_ERROR")
    assert client.get(f"{BASE}/1").json()["analysis_count"] == 0
