"""Standart uçları (sözleşme §4): liste/filtre/sayfalama, ekleme (ADMIN, 409), detay, PDF yükleme (202), index-status."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.domain.enums import IndexStatus
from tests.api.helpers import (
    ENGINEER,
    INDEX_STATUS_KEYS,
    PAGE_KEYS,
    STANDARD_KEYS,
    UUID_PDF_NAME,
    act_as,
    assert_error_shape,
    assert_utc,
    pdf_upload,
    stored_files,
)

BASE = "/api/v1/standards"
NEW_STANDARD = {
    "code": "RTCA-DO-160G", "title": "Environmental Conditions and Test Procedures for Airborne Equipment",
    "standard_type": "CIVIL", "version": "G", "issuing_body": "RTCA, Inc.", "publication_year": 2010,
    "description": "Hava aracı ekipmanları için çevresel test prosedürleri.",
}


# --------------------------------------------------------------------------------------------- GET /standards


def test_list_seed_three_standards(client: TestClient) -> None:
    r = client.get(BASE)
    assert r.status_code == 200
    body = r.json()
    assert set(body) == PAGE_KEYS
    assert body["total"] == 3 and body["page"] == 1 and body["page_size"] == 20
    codes = [s["code"] for s in body["items"]]
    assert codes == ["MIL-STD-810H", "MIL-STD-461G", "DO-178C"]
    for s in body["items"]:
        assert set(s) == STANDARD_KEYS
        assert_utc(s["created_at"])
        assert_utc(s["updated_at"])
        assert s["is_indexed"] == (s["index_status"] == "INDEXED")
    by_code = {s["code"]: s for s in body["items"]}
    assert by_code["MIL-STD-810H"]["index_status"] == "INDEXED" and by_code["MIL-STD-810H"]["has_document"]
    assert_utc(by_code["MIL-STD-810H"]["indexed_at"])
    assert by_code["MIL-STD-461G"]["index_status"] == "INDEXED"
    do = by_code["DO-178C"]
    assert do["index_status"] == "NOT_INDEXED" and not do["is_indexed"] and not do["has_document"]
    assert do["indexed_at"] is None


@pytest.mark.parametrize(("page", "page_size", "count"), [(1, 2, 2), (2, 2, 1), (3, 2, 0), (1, 100, 3)])
def test_list_pagination(client: TestClient, page: int, page_size: int, count: int) -> None:
    r = client.get(BASE, params={"page": page, "page_size": page_size})
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 3
    assert body["page"] == page and body["page_size"] == page_size
    assert len(body["items"]) == count


def test_list_pages_do_not_overlap(client: TestClient) -> None:
    p1 = client.get(BASE, params={"page": 1, "page_size": 2}).json()["items"]
    p2 = client.get(BASE, params={"page": 2, "page_size": 2}).json()["items"]
    assert {s["id"] for s in p1}.isdisjoint({s["id"] for s in p2})


@pytest.mark.parametrize(("params", "codes"), [
    ({"q": "810"}, ["MIL-STD-810H"]),
    ({"q": "mil-std"}, ["MIL-STD-810H", "MIL-STD-461G"]),  # büyük/küçük harf duyarsız
    ({"q": "software"}, ["DO-178C"]),                     # başlıkta arama
    ({"q": "yok-boyle-bir-sey"}, []),
    ({"standard_type": "CIVIL"}, ["DO-178C"]),
    ({"standard_type": "MIL"}, ["MIL-STD-810H", "MIL-STD-461G"]),
    ({"standard_type": "INTL"}, []),
    ({"index_status": "NOT_INDEXED"}, ["DO-178C"]),
    ({"index_status": "INDEXED"}, ["MIL-STD-810H", "MIL-STD-461G"]),
    ({"status": "ACTIVE"}, ["MIL-STD-810H", "MIL-STD-461G", "DO-178C"]),
    ({"status": "ARCHIVED"}, []),
    ({"q": "mil", "index_status": "INDEXED", "standard_type": "MIL"}, ["MIL-STD-810H", "MIL-STD-461G"]),
])
def test_list_filters(client: TestClient, params: dict, codes: list[str]) -> None:
    body = client.get(BASE, params=params).json()
    assert [s["code"] for s in body["items"]] == codes
    assert body["total"] == len(codes)


def test_list_filter_total_counts_all_matches_not_page(client: TestClient) -> None:
    body = client.get(BASE, params={"standard_type": "MIL", "page_size": 1}).json()
    assert body["total"] == 2 and len(body["items"]) == 1


@pytest.mark.parametrize("params", [
    {"standard_type": "XYZ"}, {"standard_type": "mil"}, {"status": "DELETED"}, {"index_status": "DONE"},
    {"page_size": 101}, {"page_size": 0}, {"page": 0}, {"page": "bir"},
])
def test_list_invalid_query_422(client: TestClient, params: dict) -> None:
    err = assert_error_shape(client.get(BASE, params=params), 422, "VALIDATION_ERROR")
    assert isinstance(err["details"], list) and err["details"]


# --------------------------------------------------------------------------------------------- POST /standards


def test_create_201(client: TestClient) -> None:
    r = client.post(BASE, json=NEW_STANDARD)
    assert r.status_code == 201, r.text
    body = r.json()
    assert set(body) == STANDARD_KEYS
    assert body["id"] == 4
    for key in ("code", "title", "standard_type", "version", "issuing_body", "publication_year", "description"):
        assert body[key] == NEW_STANDARD[key]
    assert body["status"] == "ACTIVE"
    assert body["index_status"] == "NOT_INDEXED"
    assert body["is_indexed"] is False and body["has_document"] is False
    assert body["chunk_count"] == 0 and body["requirement_count"] == 0
    assert body["page_count"] is None and body["indexed_at"] is None
    assert_utc(body["created_at"])
    assert_utc(body["updated_at"])
    # Kalıcı: detayda ve listede görünür.
    assert client.get(f"{BASE}/4").json() == body
    assert client.get(BASE).json()["total"] == 4


def test_create_minimal_body_optional_fields_null(client: TestClient) -> None:
    r = client.post(BASE, json={"code": "ISO-9001", "title": "Quality Management", "standard_type": "INTL"})
    assert r.status_code == 201
    body = r.json()
    assert body["version"] is None and body["issuing_body"] is None
    assert body["publication_year"] is None and body["description"] is None


@pytest.mark.parametrize("code", ["MIL-STD-810H", "mil-std-810h", "Mil-Std-810H", "  MIL-STD-810H  "])
def test_create_duplicate_code_case_insensitive_409(client: TestClient, code: str) -> None:
    r = client.post(BASE, json={**NEW_STANDARD, "code": code})
    err = assert_error_shape(r, 409, "CONFLICT")
    assert err["details"] is None
    assert client.get(BASE).json()["total"] == 3  # kayıt eklenmedi


def test_create_duplicate_of_new_standard_409(client: TestClient) -> None:
    assert client.post(BASE, json=NEW_STANDARD).status_code == 201
    assert_error_shape(client.post(BASE, json={**NEW_STANDARD, "code": "rtca-do-160g"}), 409, "CONFLICT")


@pytest.mark.parametrize("override", [
    {"standard_type": "NAVY"}, {"title": ""}, {"code": ""}, {"publication_year": 1800}, {"publication_year": "yıl"},
])
def test_create_invalid_body_422(client: TestClient, override: dict) -> None:
    assert_error_shape(client.post(BASE, json={**NEW_STANDARD, **override}), 422, "VALIDATION_ERROR")


def test_create_missing_required_422(client: TestClient) -> None:
    err = assert_error_shape(client.post(BASE, json={"code": "X-1"}), 422, "VALIDATION_ERROR")
    fields = " ".join(d["field"] for d in err["details"])
    assert "title" in fields and "standard_type" in fields


def test_create_as_engineer_403(app: FastAPI, client: TestClient) -> None:
    act_as(app, ENGINEER)
    assert_error_shape(client.post(BASE, json=NEW_STANDARD), 403, "FORBIDDEN")
    assert client.get(BASE).json()["total"] == 3
    # Okuma uçları ENGINEER'a açık.
    assert client.get(f"{BASE}/1").status_code == 200


# --------------------------------------------------------------------------------------------- GET /standards/{id}


def test_get_standard_200(client: TestClient) -> None:
    r = client.get(f"{BASE}/1")
    assert r.status_code == 200
    body = r.json()
    assert set(body) == STANDARD_KEYS
    assert body["code"] == "MIL-STD-810H" and body["version"] == "H" and body["publication_year"] == 2019
    assert body["page_count"] == 1089 and body["chunk_count"] == 5210 and body["requirement_count"] == 312


@pytest.mark.parametrize("sid", [999, 0, -1])
def test_get_standard_404(client: TestClient, sid: int) -> None:
    err = assert_error_shape(client.get(f"{BASE}/{sid}"), 404, "NOT_FOUND")
    assert err["details"] is None


def test_get_standard_non_int_id_422(client: TestClient) -> None:
    assert_error_shape(client.get(f"{BASE}/abc"), 422, "VALIDATION_ERROR")


# --------------------------------------------------------------------------------------------- PDF yükleme + index-status


def test_upload_document_202_pending_then_indexed(client: TestClient, pdf_bytes: bytes) -> None:
    r = client.post(f"{BASE}/3/document", files=pdf_upload(pdf_bytes, "DO-178C.pdf"))
    assert r.status_code == 202, r.text
    body = r.json()
    assert set(body) == INDEX_STATUS_KEYS
    assert body["standard_id"] == 3
    assert body["index_status"] == "PENDING"
    assert body["progress"] == 0.0
    assert body["error_message"] is None and body["finished_at"] is None

    # Arka plan görevi TestClient'ta istek sonunda çalıştı → sonraki GET'te INDEXED.
    st = client.get(f"{BASE}/3/index-status")
    assert st.status_code == 200
    status = st.json()
    assert set(status) == INDEX_STATUS_KEYS
    assert status["index_status"] == "INDEXED"
    assert status["progress"] == 1.0
    assert status["error_message"] is None
    assert status["chunk_count"] > 0 and status["page_count"] >= 1
    started, finished = assert_utc(status["started_at"]), assert_utc(status["finished_at"])
    assert started <= finished

    std = client.get(f"{BASE}/3").json()
    assert std["has_document"] is True and std["is_indexed"] is True and std["index_status"] == "INDEXED"
    assert_utc(std["indexed_at"])
    assert std["chunk_count"] == status["chunk_count"]
    assert client.get(BASE, params={"index_status": "NOT_INDEXED"}).json()["total"] == 0


def test_uploaded_standard_becomes_searchable(client: TestClient, pdf_bytes: bytes) -> None:
    before = client.post("/api/v1/search", json={"query": "general requirements", "standard_ids": [3]}).json()
    assert before["results"] == []
    assert client.post(f"{BASE}/3/document", files=pdf_upload(pdf_bytes)).status_code == 202
    after = client.post("/api/v1/search", json={"query": "general requirements", "standard_ids": [3]}).json()
    assert after["results"] and all(s["standard_id"] == 3 for s in after["results"])


def test_upload_document_for_new_standard(client: TestClient, pdf_bytes: bytes) -> None:
    sid = client.post(BASE, json=NEW_STANDARD).json()["id"]
    assert client.post(f"{BASE}/{sid}/document", files=pdf_upload(pdf_bytes)).status_code == 202
    assert client.get(f"{BASE}/{sid}/index-status").json()["index_status"] == "INDEXED"


@pytest.mark.parametrize("filename", ["kullanici_dosyasi.pdf", "../../kotu.pdf", "C:\\Windows\\x.pdf", "BÜYÜK.PDF"])
def test_upload_stored_with_uuid_name(client: TestClient, pdf_bytes: bytes, storage_dir, filename: str) -> None:
    assert client.post(f"{BASE}/3/document", files=pdf_upload(pdf_bytes, filename)).status_code == 202
    files = stored_files(storage_dir)
    assert len(files) == 1
    assert UUID_PDF_NAME.match(files[0].name), files[0].name
    assert files[0].parent == storage_dir  # klasör dışına çıkılmadı
    assert files[0].read_bytes() == pdf_bytes


def test_reupload_replaces_old_file(client: TestClient, pdf_bytes: bytes, storage_dir) -> None:
    assert client.post(f"{BASE}/1/document", files=pdf_upload(pdf_bytes)).status_code == 202
    first = stored_files(storage_dir)
    assert client.post(f"{BASE}/1/document", files=pdf_upload(pdf_bytes)).status_code == 202
    second = stored_files(storage_dir)
    assert len(second) == 1 and second != first


def test_upload_fake_pdf_415(client: TestClient, fake_pdf, storage_dir) -> None:
    r = client.post(f"{BASE}/3/document", files={"file": fake_pdf})
    assert_error_shape(r, 415, "UNSUPPORTED_FILE")
    assert stored_files(storage_dir) == []
    assert client.get(f"{BASE}/3/index-status").json()["index_status"] == "NOT_INDEXED"


@pytest.mark.parametrize(("filename", "ctype"), [
    ("rapor.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
    ("notlar.txt", "text/plain"),
    ("uzantisiz", "application/pdf"),
])
def test_upload_non_pdf_extension_415(client: TestClient, pdf_bytes: bytes, storage_dir, filename: str,
                                      ctype: str) -> None:
    r = client.post(f"{BASE}/3/document", files=pdf_upload(pdf_bytes, filename, ctype))
    assert_error_shape(r, 415, "UNSUPPORTED_FILE")
    assert stored_files(storage_dir) == []


def test_upload_too_large_413_and_no_file_left(make_client, storage_dir) -> None:
    c = make_client(MAX_UPLOAD_MB="1")
    big = b"%PDF-1.4\n" + b"0" * (1024 * 1024 + 10)
    r = c.post(f"{BASE}/3/document", files=pdf_upload(big))
    assert_error_shape(r, 413, "PAYLOAD_TOO_LARGE")
    assert stored_files(storage_dir) == []
    assert c.get(f"{BASE}/3/index-status").json()["index_status"] == "NOT_INDEXED"


def test_upload_exactly_at_limit_accepted(make_client, storage_dir) -> None:
    c = make_client(MAX_UPLOAD_MB="1")
    exact = b"%PDF-1.4\n" + b"0" * (1024 * 1024 - 9)
    assert len(exact) == 1024 * 1024
    assert c.post(f"{BASE}/3/document", files=pdf_upload(exact)).status_code == 202
    assert len(stored_files(storage_dir)) == 1


def test_upload_unknown_standard_404_no_file(client: TestClient, pdf_bytes: bytes, storage_dir) -> None:
    assert_error_shape(client.post(f"{BASE}/999/document", files=pdf_upload(pdf_bytes)), 404, "NOT_FOUND")
    assert stored_files(storage_dir) == []


@pytest.mark.parametrize("busy", [IndexStatus.PROCESSING, IndexStatus.PENDING])
def test_upload_while_indexing_409_no_file(app: FastAPI, client: TestClient, pdf_bytes: bytes, storage_dir,
                                           busy: IndexStatus) -> None:
    # Sözleşme §4: "409 zaten PROCESSING". PENDING için de 409 geliştiricinin bilinçli kararı.
    app.state.standard_repo.get(3).index_status = busy
    assert_error_shape(client.post(f"{BASE}/3/document", files=pdf_upload(pdf_bytes)), 409, "CONFLICT")
    assert stored_files(storage_dir) == []


def test_upload_missing_file_422(client: TestClient) -> None:
    assert_error_shape(client.post(f"{BASE}/3/document"), 422, "VALIDATION_ERROR")


def test_upload_as_engineer_403_no_file(app: FastAPI, client: TestClient, pdf_bytes: bytes, storage_dir) -> None:
    act_as(app, ENGINEER)
    assert_error_shape(client.post(f"{BASE}/3/document", files=pdf_upload(pdf_bytes)), 403, "FORBIDDEN")
    assert stored_files(storage_dir) == []
    # index-status okuma ucu ENGINEER'a açık.
    assert client.get(f"{BASE}/3/index-status").status_code == 200


def test_index_status_seed_indexed(client: TestClient) -> None:
    body = client.get(f"{BASE}/1/index-status").json()
    assert body["index_status"] == "INDEXED" and body["progress"] == 1.0
    assert body["page_count"] == 1089 and body["chunk_count"] == 5210
    assert_utc(body["started_at"])
    assert_utc(body["finished_at"])


def test_index_status_not_indexed(client: TestClient) -> None:
    body = client.get(f"{BASE}/3/index-status").json()
    assert body["index_status"] == "NOT_INDEXED"
    assert body["progress"] == 0.0 and body["started_at"] is None and body["finished_at"] is None


def test_index_status_404(client: TestClient) -> None:
    assert_error_shape(client.get(f"{BASE}/999/index-status"), 404, "NOT_FOUND")


def test_indexing_failure_recorded_as_failed(app: FastAPI, client: TestClient, pdf_bytes: bytes) -> None:
    def boom(*_args, **_kwargs):
        raise RuntimeError("iç hata C:\\gizli\\yol")

    app.state.search.index_document = boom
    assert client.post(f"{BASE}/3/document", files=pdf_upload(pdf_bytes)).status_code == 202
    status = client.get(f"{BASE}/3/index-status").json()
    assert status["index_status"] == "FAILED"
    assert status["error_message"] and "gizli" not in status["error_message"]
    assert_utc(status["finished_at"])
    assert client.get(f"{BASE}/3").json()["is_indexed"] is False


# --------------------------------------------------------------------------------------------- yalnız boşluk metinler (düzeltilmiş bulgu)


def test_create_whitespace_only_code_422(client: TestClient) -> None:
    r = client.post(BASE, json={**NEW_STANDARD, "code": "   "})
    assert_error_shape(r, 422, "VALIDATION_ERROR")


def test_create_whitespace_only_title_422(client: TestClient) -> None:
    r = client.post(BASE, json={**NEW_STANDARD, "title": "   "})
    assert_error_shape(r, 422, "VALIDATION_ERROR")


def test_create_code_trimmed_then_case_insensitive_409(client: TestClient) -> None:
    r = client.post(BASE, json={**NEW_STANDARD, "code": "  NEW-1  "})
    assert r.status_code == 201, r.text
    assert r.json()["code"] == "NEW-1"
    assert client.get(f"{BASE}/{r.json()['id']}").json()["code"] == "NEW-1"
    assert_error_shape(client.post(BASE, json={**NEW_STANDARD, "code": "new-1"}), 409, "CONFLICT")
    assert_error_shape(client.post(BASE, json={**NEW_STANDARD, "code": " New-1 "}), 409, "CONFLICT")


# --------------------------------------------------------------------------------------------- Türkçe büyük/küçük harf araması


@pytest.mark.parametrize("q", ["mil-std", "MIL", "Mil-Std", "mil"])
def test_list_q_mil_case_insensitive(client: TestClient, q: str) -> None:
    body = client.get(BASE, params={"q": q}).json()
    assert [s["code"] for s in body["items"]] == ["MIL-STD-810H", "MIL-STD-461G"]
    assert body["total"] == 2


@pytest.mark.parametrize(("q", "code"), [("Mil-Std-810h", "MIL-STD-810H"), ("810", "MIL-STD-810H"),
                                         ("do-178c", "DO-178C"), ("SOFTWARE", "DO-178C"),
                                         ("İNTERFERENCE", "MIL-STD-461G")])
def test_list_q_single_match(client: TestClient, q: str, code: str) -> None:
    assert [s["code"] for s in client.get(BASE, params={"q": q}).json()["items"]] == [code]


def test_list_q_turkish_in_new_standard_title(client: TestClient) -> None:
    sid = client.post(BASE, json={**NEW_STANDARD, "code": "TR-1", "title": "Işık ve Isı Şartnamesi"}).json()["id"]
    for q in ("IŞIK", "ışık", "ISIK", "ısı şartnamesi", "ŞARTNAME"):
        ids = [s["id"] for s in client.get(BASE, params={"q": q}).json()["items"]]
        assert ids == [sid], q
