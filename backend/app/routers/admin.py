from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status

from .. import db
from ..config import get_settings
from ..deps import require_admin
from ..domains import clean_domains
from ..rag.ingest import DuplicateDocument, register_document, worker
from ..schemas import DocumentOut, DocumentUpdate
from .common import DOC_COLS, get_document

router = APIRouter(prefix="/api/admin", tags=["Yönetim (admin)"])


@router.get("/stats", summary="Sistem özeti")
def stats(_: dict = Depends(require_admin)):
    s = get_settings()
    row = db.fetch_one(
        """SELECT (SELECT count(*) FROM users) AS users,
                  (SELECT count(*) FROM documents) AS documents,
                  (SELECT count(*) FROM chunks) AS chunks,
                  (SELECT count(*) FROM chunks WHERE embedding IS NOT NULL) AS embedded,
                  (SELECT count(*) FROM conversations) AS conversations,
                  (SELECT count(*) FROM messages WHERE role = 'user') AS questions"""
    )
    return {**row, "llm_enabled": s.llm_enabled, "model": s.gemini_model, "embedding_model": s.embedding_model,
            "worker_busy": worker.is_busy()}


@router.get("/documents", response_model=list[DocumentOut], summary="Tüm dokümanlar ve işlenme durumu")
def all_documents(_: dict = Depends(require_admin)):
    return db.fetch_all(f"SELECT {DOC_COLS} FROM documents d ORDER BY d.created_at DESC")


@router.post("/documents", response_model=DocumentOut, status_code=status.HTTP_201_CREATED, summary="PDF yükle")
def upload_document(
    file: UploadFile = File(..., description="Standart PDF dosyası"),
    code: str = Form(..., min_length=2, max_length=80, examples=["MIL-STD-882E"]),
    title: str = Form(..., min_length=2, max_length=300),
    issuer: str = Form(""),
    category: str = Form("civil", pattern="^(civil|defense)$"),
    domains: str = Form("", description="Virgülle ayrılmış: software,safety,..."),
    language: str = Form("en", pattern="^(en|tr)$"),
    version: str = Form(""),
    published_on: str = Form(""),
    source_url: str = Form(""),
    admin: dict = Depends(require_admin),
):
    s = get_settings()
    if not (file.filename or "").lower().endswith(".pdf"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Yalnızca PDF dosyaları yüklenebilir")
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf", dir=s.storage_dir) as tmp:
        shutil.copyfileobj(file.file, tmp, length=1 << 20)
        tmp_path = Path(tmp.name)
    try:
        size_mb = tmp_path.stat().st_size / 1e6
        if size_mb > s.max_upload_mb:
            raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, f"Dosya {s.max_upload_mb} MB sınırını aşıyor")
        with open(tmp_path, "rb") as f:
            if f.read(5) != b"%PDF-":
                raise HTTPException(status.HTTP_400_BAD_REQUEST, "Dosya geçerli bir PDF değil")
        meta = {
            "code": code.strip(), "title": title.strip(), "issuer": issuer.strip(), "category": category,
            "domains": clean_domains([d.strip() for d in domains.split(",")]), "language": language,
            "version": version.strip(), "published_on": published_on.strip(), "source_url": source_url.strip(),
        }
        try:
            doc_id = register_document(tmp_path, meta, uploaded_by=admin["id"], move=True)
        except DuplicateDocument as e:
            raise HTTPException(status.HTTP_409_CONFLICT, f"Bu PDF zaten yüklü (doküman #{e.document_id})")
    finally:
        tmp_path.unlink(missing_ok=True)
    worker.enqueue(doc_id)
    return get_document(doc_id)


@router.patch("/documents/{doc_id}", response_model=DocumentOut, summary="Doküman bilgilerini düzenle")
def update_document(doc_id: int, body: DocumentUpdate, _: dict = Depends(require_admin)):
    get_document(doc_id)
    data = body.model_dump(exclude_none=True)
    if "domains" in data:
        data["domains"] = clean_domains(data["domains"])
    if data:
        sets = ", ".join(f"{k} = %({k})s" for k in data)
        db.execute(f"UPDATE documents SET {sets}, updated_at = now() WHERE id = %(id)s", {**data, "id": doc_id})
        if "language" in data or "code" in data:
            worker.enqueue(doc_id, reparse=True)  # tam metin dizini dile/koda bağlı
    return get_document(doc_id)


@router.post("/documents/{doc_id}/reprocess", response_model=DocumentOut, summary="Yeniden ayrıştır ve indeksle")
def reprocess(doc_id: int, _: dict = Depends(require_admin)):
    get_document(doc_id)
    db.execute("UPDATE documents SET status = 'queued', error = NULL WHERE id = %s", (doc_id,))
    worker.enqueue(doc_id, reparse=True)
    return get_document(doc_id)


@router.delete("/documents/{doc_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Dokümanı sil")
def delete_document(doc_id: int, _: dict = Depends(require_admin)):
    row = db.fetch_one("SELECT file_name FROM documents WHERE id = %s", (doc_id,))
    if not row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Doküman bulunamadı")
    db.execute("DELETE FROM documents WHERE id = %s", (doc_id,))
    (get_settings().storage_dir / row["file_name"]).unlink(missing_ok=True)
