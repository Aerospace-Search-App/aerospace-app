from __future__ import annotations

from fastapi import HTTPException, status

from .. import db

DOC_COLS = """d.id, d.code, d.title, d.issuer, d.category, d.domains, d.language, d.version, d.published_on,
              d.summary, d.source_url, d.page_count, d.chunk_count, d.embedded_count, d.status, d.error, d.created_at"""


def saved_doc_ids(user_id: int) -> set[int]:
    return {r["document_id"] for r in db.fetch_all(
        "SELECT document_id FROM saved_items WHERE user_id = %s AND chunk_id IS NULL", (user_id,)
    )}


def get_document(doc_id: int) -> dict:
    row = db.fetch_one(f"SELECT {DOC_COLS} FROM documents d WHERE d.id = %s", (doc_id,))
    if not row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Doküman bulunamadı")
    return row


def get_own_project(project_id: int, user_id: int) -> dict:
    row = db.fetch_one("SELECT * FROM projects WHERE id = %s AND user_id = %s", (project_id, user_id))
    if not row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Proje bulunamadı")
    return row
