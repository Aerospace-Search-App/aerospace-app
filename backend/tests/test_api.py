"""Uçtan uca API testleri — gerçek PostgreSQL + pgvector gerekir.

TEST_DATABASE_URL=postgresql://postgres:postgres@localhost:5432/aerostd_test pytest -q
"""
from __future__ import annotations

import hashlib
import math
import os
import time
from pathlib import Path

import psycopg
import pytest

TEST_DB = os.getenv("TEST_DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/aerostd_test")
os.environ.update(DATABASE_URL=TEST_DB, AUTO_SEED="false", GEMINI_API_KEY="", ADMIN_EMAIL="admin@test.local",
                  ADMIN_PASSWORD="Admin12345!", JWT_SECRET="test-secret-test-secret-test-secret-123")


def _reset_db():
    base = TEST_DB.rsplit("/", 1)[0] + "/postgres"
    name = TEST_DB.rsplit("/", 1)[1]
    with psycopg.connect(base, autocommit=True) as c:
        c.execute(f"DROP DATABASE IF EXISTS {name} WITH (FORCE)")
        c.execute(f"CREATE DATABASE {name}")


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    _reset_db()
    storage = tmp_path_factory.mktemp("storage")
    os.environ["STORAGE_DIR"] = str(storage)
    from app.config import get_settings

    get_settings.cache_clear()
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as c:
        yield c
    from app import db

    db.close_pool()


def auth(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="module")
def admin_token(client):
    r = client.post("/api/auth/login", json={"email": "admin@test.local", "password": "Admin12345!"})
    assert r.status_code == 200, r.text
    assert r.json()["user"]["role"] == "admin"
    return r.json()["access_token"]


@pytest.fixture(scope="module")
def user_token(client):
    r = client.post("/api/auth/register", json={"username": "halil.t", "full_name": "Halil Test", "email": "Halil@Example.com", "password": "Parola123", "accept_terms": True})
    assert r.status_code == 201, r.text
    return r.json()["access_token"]


def wait_ready(client, token, doc_id, statuses=("lexical_only", "ready"), timeout=60):
    t0 = time.time()
    while time.time() - t0 < timeout:
        docs = client.get("/api/admin/documents", headers=auth(token)).json()
        d = next(x for x in docs if x["id"] == doc_id)
        if d["status"] in statuses:
            return d
        if d["status"] == "failed":
            raise AssertionError(d["error"])
        time.sleep(0.3)
    raise TimeoutError(d)


def upload(client, token, path: Path, **meta):
    with open(path, "rb") as f:
        return client.post(
            "/api/admin/documents",
            headers=auth(token),
            files={"file": (path.name, f, "application/pdf")},
            data={"title": meta.pop("title", "Test"), **meta},
        )


# ---------------------------------------------------------------------------
def test_auth_flow(client, user_token):
    r = client.get("/api/auth/me", headers=auth(user_token))
    assert r.status_code == 200 and r.json()["email"] == "halil@example.com"
    assert client.get("/api/auth/me").status_code == 401
    assert client.get("/api/auth/me", headers=auth("bozuk.token.x")).status_code == 401
    dup = client.post("/api/auth/register", json={"username": "baska", "email": "halil@example.com", "password": "Parola123", "accept_terms": True})
    assert dup.status_code == 409
    dup_user = client.post("/api/auth/register", json={"username": "HALIL.T", "email": "yeni@example.com", "password": "Parola123", "accept_terms": True})
    assert dup_user.status_code == 409 and "kullanıcı adı" in dup_user.json()["detail"]
    weak = client.post("/api/auth/register", json={"username": "xy_z", "email": "a@b.co", "password": "sadeceharf", "accept_terms": True})
    assert weak.status_code == 422 and "rakam" in weak.json()["detail"]
    no_terms = client.post("/api/auth/register", json={"username": "xyz", "email": "a@b.co", "password": "Parola123"})
    assert no_terms.status_code == 422 and "KVKK" in no_terms.json()["detail"]
    bad_name = client.post("/api/auth/register", json={"username": "a b", "email": "a@b.co", "password": "Parola123", "accept_terms": True})
    assert bad_name.status_code == 422
    # kullanıcı adıyla giriş ve profil güncelleme
    by_user = client.post("/api/auth/login", json={"email": "halil.t", "password": "Parola123"})
    assert by_user.status_code == 200 and by_user.json()["user"]["username"] == "halil.t"
    upd = client.patch("/api/auth/me", headers=auth(user_token), json={"username": "halil.turan"})
    assert upd.status_code == 200 and upd.json()["username"] == "halil.turan"
    assert client.patch("/api/auth/me", headers=auth(user_token), json={"username": "admin"}).status_code == 409
    bad = client.post("/api/auth/login", json={"email": "halil@example.com", "password": "yanlis123"})
    assert bad.status_code == 401
    ok = client.post("/api/auth/login", json={"email": "HALIL@example.com", "password": "Parola123"})
    assert ok.status_code == 200


def test_admin_required(client, user_token):
    assert client.get("/api/admin/stats", headers=auth(user_token)).status_code == 403


def test_upload_parse_search_chat(client, admin_token, user_token, tmp_path):
    from .samples import make_milstd, make_shgm

    r = upload(client, admin_token, make_milstd(tmp_path / "mil.pdf"), code="MIL-STD-999X", title="System Safety Test",
               issuer="DoD", category="defense", domains="safety,systems")
    assert r.status_code == 201, r.text
    mil = wait_ready(client, admin_token, r.json()["id"])
    assert mil["status"] == "lexical_only" and mil["chunk_count"] >= 8

    r = upload(client, admin_token, make_shgm(tmp_path / "sht.pdf"), code="SHT-999", title="Bakım Kuruluşları Talimatı",
               issuer="SHGM", category="civil", domains="maintenance", language="tr")
    assert r.status_code == 201, r.text
    sht = wait_ready(client, admin_token, r.json()["id"])

    # Aynı PDF tekrar yüklenemez
    dup = upload(client, admin_token, tmp_path / "mil.pdf", code="DUP", title="dup")
    assert dup.status_code == 409
    # PDF olmayan dosya reddedilir
    bad = tmp_path / "x.pdf"
    bad.write_text("merhaba")
    assert upload(client, admin_token, bad, code="BAD", title="bad").status_code == 400

    docs = client.get("/api/documents", headers=auth(user_token)).json()
    assert {d["code"] for d in docs} == {"MIL-STD-999X", "SHT-999"}
    assert client.get("/api/documents?category=defense", headers=auth(user_token)).json()[0]["code"] == "MIL-STD-999X"

    # Hibrit arama (anahtar yok → lexical)
    s = client.post("/api/search", headers=auth(user_token), json={"query": "closed-loop hazard tracking system"}).json()
    assert s["mode"] == "lexical"
    assert s["hits"][0]["clause_ref"] == "4.1.1", s["hits"][:2]
    # Türkçe kök bulma (turkish tsvector): "personelin" → "personel"
    s = client.post("/api/search", headers=auth(user_token), json={"query": "sertifikalandırma personelinin lisansı"}).json()
    assert s["hits"] and s["hits"][0]["code"] == "SHT-999" and s["hits"][0]["clause_ref"] == "Madde 3"

    # Madde listesi ve kaynak görüntüleyici
    clauses = client.get(f"/api/documents/{mil['id']}/clauses", headers=auth(user_token)).json()
    assert [c["clause_ref"] for c in clauses if c["clause_ref"]][:3] == ["1.1", "1.2", "2"]
    cid = next(c["id"] for c in clauses if c["clause_ref"] == "4.1.1")
    src = client.get(f"/api/chunks/{cid}", headers=auth(user_token)).json()
    assert src["chunk"]["heading"].startswith("Hazard tracking") and src["prev_id"] and src["next_id"]
    png = client.get(src["page_image_url"])
    assert png.status_code == 200 and png.content[:4] == b"\x89PNG"
    pdf = client.get(src["file_url"].split("#")[0])
    assert pdf.status_code == 200 and pdf.content[:5] == b"%PDF-"
    assert client.get(f"/api/documents/{mil['id']}/file?token=yanlis").status_code == 401
    assert client.get(f"/api/documents/{sht['id']}/file?" + src["file_url"].split("?")[1].split("#")[0]).status_code == 403

    # Sohbet (kaynaklı cevap, alıntı modu) ve geçmiş
    r = client.post("/api/chat", headers=auth(user_token), json={"message": "Hazard tracking system nasıl kurulmalı?"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["answer"]["citations"] and body["answer"]["citations"][0]["code"] == "MIL-STD-999X"
    assert "[1]" in body["answer"]["content"]
    conv_id = body["conversation_id"]
    r2 = client.post("/api/chat", headers=auth(user_token), json={"message": "Risk assessment severity", "conversation_id": conv_id})
    assert r2.status_code == 200 and r2.json()["conversation_id"] == conv_id
    convs = client.get("/api/conversations", headers=auth(user_token)).json()
    assert len(convs) == 1 and convs[0]["message_count"] == 4
    detail = client.get(f"/api/conversations/{conv_id}", headers=auth(user_token)).json()
    assert [m["role"] for m in detail["messages"]] == ["user", "assistant", "user", "assistant"]
    assert client.patch(f"/api/conversations/{conv_id}", headers=auth(user_token), json={"title": "Tehlike takibi"}).json()["title"] == "Tehlike takibi"
    nohit = client.post("/api/chat", headers=auth(user_token), json={"message": "zzqx qwvv"}).json()
    assert nohit["answer"]["citations"] == [] and "bulamadım" in nohit["answer"]["content"]

    # Kaydetme
    r = client.post("/api/saved", headers=auth(user_token), json={"document_id": mil["id"]})
    assert r.status_code == 201
    r = client.post("/api/saved", headers=auth(user_token), json={"document_id": mil["id"], "chunk_id": cid, "note": "önemli"})
    assert r.status_code == 201 and r.json()["clause_ref"] == "4.1.1"
    again = client.post("/api/saved", headers=auth(user_token), json={"document_id": mil["id"], "chunk_id": cid, "note": "çok önemli"})
    assert again.status_code == 201 and again.json()["id"] == r.json()["id"] and again.json()["note"] == "çok önemli"
    saved = client.get("/api/saved", headers=auth(user_token)).json()
    assert len(saved) == 2
    assert client.get(f"/api/chunks/{cid}", headers=auth(user_token)).json()["is_saved"] is True
    assert any(d["is_saved"] for d in client.get("/api/documents", headers=auth(user_token)).json())
    client.delete(f"/api/saved?document_id={mil['id']}", headers=auth(user_token))
    assert len(client.get("/api/saved", headers=auth(user_token)).json()) == 1
    bad_chunk = client.post("/api/saved", headers=auth(user_token), json={"document_id": sht["id"], "chunk_id": cid})
    assert bad_chunk.status_code == 404

    # Projeler ve öneriler
    r = client.post("/api/projects", headers=auth(user_token), json={
        "name": "İHA uçuş kontrol emniyet analizi", "description": "Hazard analysis and risk assessment for a UAV",
        "category": "both", "domains": ["safety", "olmayan-alan"]})
    assert r.status_code == 201 and r.json()["domains"] == ["safety"]
    pid = r.json()["id"]
    recs = client.get(f"/api/projects/{pid}/recommendations", headers=auth(user_token)).json()
    assert recs and recs[0]["document"]["code"] == "MIL-STD-999X" and recs[0]["clauses"]
    assert any("Alan eşleşmesi" in x for x in recs[0]["reasons"])
    r = client.post("/api/chat", headers=auth(user_token), json={"message": "hazard severity categories", "project_id": pid})
    assert r.status_code == 200
    assert client.get(f"/api/conversations?project_id={pid}", headers=auth(user_token)).json()[0]["project_name"]
    assert client.get("/api/projects", headers=auth(user_token)).json()[0]["conversation_count"] == 1

    # Başka kullanıcı erişemez
    other = client.post("/api/auth/register", json={"username": "diger", "email": "o@x.io", "password": "Parola123", "accept_terms": True}).json()["access_token"]
    assert client.get(f"/api/projects/{pid}", headers=auth(other)).status_code == 404
    assert client.get(f"/api/conversations/{conv_id}", headers=auth(other)).status_code == 404

    # Yanıt ve sohbet kaydetme, kaynak filtresi
    ans_id = body["answer"]["id"]
    assert client.put(f"/api/messages/{ans_id}/save", headers=auth(user_token)).status_code == 204
    assert client.put(f"/api/messages/{ans_id}/save", headers=auth(other)).status_code == 404
    answers = client.get("/api/saved/answers", headers=auth(user_token)).json()
    assert len(answers) == 1 and answers[0]["question"].startswith("Hazard tracking") and answers[0]["sources"]
    assert answers[0]["sources"][0] == "DoD • MIL-STD-999X"
    assert client.get("/api/saved/answers?q=zzzz", headers=auth(user_token)).json() == []
    detail = client.get(f"/api/conversations/{conv_id}", headers=auth(user_token)).json()
    assert detail["messages"][1]["saved"] is True and detail["sources"]
    client.delete(f"/api/messages/{ans_id}/save", headers=auth(user_token))
    assert client.get("/api/saved/answers", headers=auth(user_token)).json() == []
    client.put(f"/api/conversations/{conv_id}/star", headers=auth(user_token))
    starred = client.get("/api/conversations?starred=true", headers=auth(user_token)).json()
    assert [c["id"] for c in starred] == [conv_id] and starred[0]["starred"]
    assert client.get("/api/conversations?q=Tehlike", headers=auth(user_token)).json()[0]["id"] == conv_id
    iss = client.get("/api/meta/issuers", headers=auth(user_token)).json()
    assert {i["issuer"] for i in iss} == {"DoD", "SHGM"}
    filt = client.post("/api/chat", headers=auth(user_token), json={"message": "hazard tracking personel", "issuer": "SHGM"}).json()
    assert all(c["code"] == "SHT-999" for c in filt["answer"]["citations"])
    assert filt["answer"]["meta"]["sources_scanned"] >= 1

    stats = client.get("/api/admin/stats", headers=auth(admin_token)).json()
    assert stats["documents"] == 2 and stats["questions"] == 5 and stats["llm_enabled"] is False
    assert client.get("/api/health").json()["documents"] == 2
    assert client.get("/docs").status_code == 200
    assert client.get("/admin/").status_code == 200


# ---------------------------------------------------------------------------
# Gemini açıkken (sahte istemci ile) hibrit arama + kaynaklı cevap
# ---------------------------------------------------------------------------
def _fake_vec(text: str, dim: int = 768) -> list[float]:
    v = [0.0] * dim
    for w in text.lower().split():
        h = int(hashlib.md5(w.strip(".,:;()").encode()).hexdigest(), 16)
        v[h % dim] += 1.0
    n = math.sqrt(sum(x * x for x in v)) or 1
    return [x / n for x in v]


def test_with_fake_gemini(client, admin_token, user_token, monkeypatch, tmp_path):
    from app.config import get_settings
    from app.rag import gemini

    s = get_settings()
    monkeypatch.setattr(s, "gemini_api_key", "fake-key")
    monkeypatch.setattr(gemini, "embed_documents", lambda items: [_fake_vec(f"{t} {x}") for t, x in items])
    monkeypatch.setattr(gemini, "embed_query", lambda q: _fake_vec(q))
    monkeypatch.setattr(gemini, "analyze_query", lambda q, h: {"standalone": q, "terms": ["hazard", "severity"], "codes": ["MIL-STD-999X"]})
    monkeypatch.setattr(gemini, "make_title", lambda q: "Sahte başlık")
    monkeypatch.setattr(gemini, "_generate", lambda *a, **k: "Özet.")
    captured = {}

    def fake_answer(q, sources, history, project):
        captured["n"] = len(sources)
        return "Tehlikeler kapalı döngü bir sistemle izlenmelidir [1]. Ayrıca risk değerlendirilir [2][9]."

    monkeypatch.setattr(gemini, "generate_answer", fake_answer)

    docs = client.get("/api/admin/documents", headers=auth(admin_token)).json()
    mil = next(d for d in docs if d["code"] == "MIL-STD-999X")
    client.post(f"/api/admin/documents/{mil['id']}/reprocess", headers=auth(admin_token))
    d = wait_ready(client, admin_token, mil["id"], statuses=("ready",))
    assert d["embedded_count"] == d["chunk_count"] > 0

    s_out = client.post("/api/search", headers=auth(user_token), json={"query": "hazard tracking closed loop"}).json()
    assert s_out["mode"] == "hybrid"
    assert any(h["vector_rank"] for h in s_out["hits"])

    r = client.post("/api/chat", headers=auth(user_token), json={"message": "Tehlike takibi nasıl yapılır?"}).json()
    ans = r["answer"]
    assert "[9]" not in ans["content"]  # geçersiz atıf temizlendi
    assert [c["n"] for c in ans["citations"]] == [1, 2]
    assert ans["meta"]["mode"] == "hybrid" and ans["meta"]["model"]
    assert r["title"] == "Sahte başlık"
