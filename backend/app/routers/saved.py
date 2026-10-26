from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from .. import db
from ..deps import get_current_user
from ..schemas import SavedIn, SavedOut
from .common import get_document, get_own_project

router = APIRouter(prefix="/api/saved", tags=["Kaydedilen standartlar"])

SELECT = """
SELECT s.id, s.document_id, s.chunk_id, s.project_id, s.note, s.created_at,
       d.code, d.title AS doc_title, d.issuer, d.category,
       c.clause_ref, c.heading, c.page_start, left(c.content, 220) AS snippet
FROM saved_items s JOIN documents d ON d.id = s.document_id LEFT JOIN chunks c ON c.id = s.chunk_id
WHERE s.user_id = %(u)s {extra}
ORDER BY s.created_at DESC
"""


@router.get("", response_model=list[SavedOut], summary="Kaydettiklerim")
def list_saved(project_id: int | None = None, user: dict = Depends(get_current_user)):
    extra, params = "", {"u": user["id"]}
    if project_id:
        extra, params["p"] = "AND s.project_id = %(p)s", project_id
    return db.fetch_all(SELECT.format(extra=extra), params)


@router.post("", response_model=SavedOut, status_code=status.HTTP_201_CREATED, summary="Standart/madde kaydet")
def save_item(body: SavedIn, user: dict = Depends(get_current_user)):
    get_document(body.document_id)
    if body.chunk_id is not None:
        ok = db.fetch_one("SELECT 1 FROM chunks WHERE id = %s AND document_id = %s", (body.chunk_id, body.document_id))
        if not ok:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Madde bu standarda ait değil")
    if body.project_id is not None:
        get_own_project(body.project_id, user["id"])
    row = db.fetch_one(
        """INSERT INTO saved_items (user_id, document_id, chunk_id, project_id, note)
           VALUES (%s, %s, %s, %s, %s)
           ON CONFLICT (user_id, document_id, chunk_id) DO UPDATE
             SET note = EXCLUDED.note, project_id = COALESCE(EXCLUDED.project_id, saved_items.project_id)
           RETURNING id""",
        (user["id"], body.document_id, body.chunk_id, body.project_id, body.note.strip()),
    )
    return db.fetch_one(SELECT.format(extra="AND s.id = %(id)s"), {"u": user["id"], "id": row["id"]})


@router.delete("/{saved_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Kaydı kaldır")
def delete_saved(saved_id: int, user: dict = Depends(get_current_user)):
    db.execute("DELETE FROM saved_items WHERE id = %s AND user_id = %s", (saved_id, user["id"]))


@router.delete("", status_code=status.HTTP_204_NO_CONTENT, summary="Doküman/madde kaydını kaldır")
def unsave(document_id: int, chunk_id: int | None = None, user: dict = Depends(get_current_user)):
    db.execute(
        "DELETE FROM saved_items WHERE user_id = %s AND document_id = %s AND chunk_id IS NOT DISTINCT FROM %s",
        (user["id"], document_id, chunk_id),
    )
