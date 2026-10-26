from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from psycopg.types.json import Jsonb
from pydantic import BaseModel, Field

from .. import db
from ..deps import get_current_user
from ..rag import gemini
from ..rag.answer import answer_question
from ..schemas import ChatIn, ChatOut, ConversationDetail, ConversationOut, MessageOut, SavedAnswerOut
from .common import get_own_project

router = APIRouter(prefix="/api", tags=["Sohbet (RAG)"])


class RenameIn(BaseModel):
    title: str = Field(min_length=1, max_length=80)


def _msg(row: dict) -> dict:
    return {**row, "saved": row.get("saved_at") is not None}


def _own_conversation(conv_id: int, user_id: int) -> dict:
    row = db.fetch_one("SELECT * FROM conversations WHERE id = %s AND user_id = %s", (conv_id, user_id))
    if not row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Sohbet bulunamadı")
    return row


def _sources_of(citations: list[dict]) -> list[str]:
    out: list[str] = []
    for c in citations or []:
        label = " • ".join(x for x in (c.get('issuer') or '', c['code']) if x)
        if label not in out:
            out.append(label)
    return out


@router.post("/chat", response_model=ChatOut, summary="Soru sor — kaynaklı cevap al")
def chat(body: ChatIn, user: dict = Depends(get_current_user)):
    question = body.message.strip()
    if not question:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Mesaj boş olamaz")

    if body.conversation_id:
        conv = _own_conversation(body.conversation_id, user["id"])
        history = db.fetch_all(
            "SELECT role, content FROM messages WHERE conversation_id = %s ORDER BY id DESC LIMIT 8", (conv["id"],)
        )[::-1]
    else:
        conv, history = None, []

    project_id = body.project_id or (conv["project_id"] if conv else None)
    project = get_own_project(project_id, user["id"]) if project_id else None
    saved_docs = [r["document_id"] for r in db.fetch_all(
        "SELECT DISTINCT document_id FROM saved_items WHERE user_id = %s", (user["id"],)
    )]

    answer, citations, meta = answer_question(
        question, history, project=project, category=body.category, boost_document_ids=saved_docs, issuer=body.issuer
    )

    with db.get_conn() as conn:
        with conn.transaction():
            if conv is None:
                conv = conn.execute(
                    "INSERT INTO conversations (user_id, project_id, title) VALUES (%s, %s, %s) RETURNING *",
                    (user["id"], project_id, gemini.make_title(question)),
                ).fetchone()
            elif body.project_id and conv["project_id"] != body.project_id:
                conn.execute("UPDATE conversations SET project_id = %s WHERE id = %s", (body.project_id, conv["id"]))
            um = conn.execute(
                "INSERT INTO messages (conversation_id, role, content) VALUES (%s, 'user', %s) RETURNING *",
                (conv["id"], question),
            ).fetchone()
            am = conn.execute(
                "INSERT INTO messages (conversation_id, role, content, citations, meta) VALUES (%s, 'assistant', %s, %s, %s) RETURNING *",
                (conv["id"], answer, Jsonb(citations), Jsonb(meta)),
            ).fetchone()
            conn.execute("UPDATE conversations SET updated_at = now() WHERE id = %s", (conv["id"],))

    return ChatOut(conversation_id=conv["id"], title=conv["title"], user_message=MessageOut(**_msg(um)),
                   answer=MessageOut(**_msg(am)))


CONV_SQL = """
SELECT c.id, c.title, c.project_id, p.name AS project_name, c.created_at, c.updated_at,
       c.starred_at IS NOT NULL AS starred,
       (SELECT content FROM messages m WHERE m.conversation_id = c.id ORDER BY id DESC LIMIT 1) AS last_message,
       (SELECT citations FROM messages m WHERE m.conversation_id = c.id AND m.role = 'assistant'
          AND jsonb_array_length(m.citations) > 0 ORDER BY id DESC LIMIT 1) AS last_citations,
       (SELECT count(*) FROM messages m WHERE m.conversation_id = c.id) AS message_count
FROM conversations c LEFT JOIN projects p ON p.id = c.project_id
WHERE c.user_id = %(u)s {extra}
ORDER BY c.updated_at DESC LIMIT 200
"""


def _conv(row: dict) -> dict:
    return {**row, "sources": _sources_of(row.pop("last_citations", None) or [])[:2]}


@router.get("/conversations", response_model=list[ConversationOut], summary="Sohbet geçmişi")
def list_conversations(
    project_id: int | None = None,
    q: str | None = Query(None, max_length=100, description="Başlık veya mesajlarda ara"),
    starred: bool | None = None,
    user: dict = Depends(get_current_user),
):
    params: dict = {"u": user["id"]}
    extra = []
    if project_id:
        extra.append("AND c.project_id = %(p)s")
        params["p"] = project_id
    if starred:
        extra.append("AND c.starred_at IS NOT NULL")
    if q and q.strip():
        extra.append("AND (c.title ILIKE %(q)s OR EXISTS (SELECT 1 FROM messages m WHERE m.conversation_id = c.id AND m.content ILIKE %(q)s))")
        params["q"] = f"%{q.strip()}%"
    return [_conv(r) for r in db.fetch_all(CONV_SQL.format(extra=" ".join(extra)), params)]


@router.get("/conversations/{conv_id}", response_model=ConversationDetail, summary="Sohbet detayı")
def get_conversation(conv_id: int, user: dict = Depends(get_current_user)):
    _own_conversation(conv_id, user["id"])
    conv = _conv(db.fetch_one(CONV_SQL.format(extra="AND c.id = %(id)s"), {"u": user["id"], "id": conv_id}))
    msgs = [_msg(m) for m in db.fetch_all("SELECT * FROM messages WHERE conversation_id = %s ORDER BY id", (conv_id,))]
    return {**conv, "messages": msgs}


@router.patch("/conversations/{conv_id}", response_model=ConversationOut, summary="Sohbet başlığını değiştir")
def rename_conversation(conv_id: int, body: RenameIn, user: dict = Depends(get_current_user)):
    _own_conversation(conv_id, user["id"])
    db.execute("UPDATE conversations SET title = %s WHERE id = %s", (body.title.strip(), conv_id))
    return _conv(db.fetch_one(CONV_SQL.format(extra="AND c.id = %(id)s"), {"u": user["id"], "id": conv_id}))


@router.put("/conversations/{conv_id}/star", status_code=status.HTTP_204_NO_CONTENT, summary="Sohbeti kaydet")
def star_conversation(conv_id: int, user: dict = Depends(get_current_user)):
    _own_conversation(conv_id, user["id"])
    db.execute("UPDATE conversations SET starred_at = COALESCE(starred_at, now()) WHERE id = %s", (conv_id,))


@router.delete("/conversations/{conv_id}/star", status_code=status.HTTP_204_NO_CONTENT, summary="Sohbet kaydını kaldır")
def unstar_conversation(conv_id: int, user: dict = Depends(get_current_user)):
    _own_conversation(conv_id, user["id"])
    db.execute("UPDATE conversations SET starred_at = NULL WHERE id = %s", (conv_id,))


@router.delete("/conversations/{conv_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Sohbeti sil")
def delete_conversation(conv_id: int, user: dict = Depends(get_current_user)):
    _own_conversation(conv_id, user["id"])
    db.execute("DELETE FROM conversations WHERE id = %s", (conv_id,))


# --- Kaydedilen yanıtlar ----------------------------------------------------
def _own_answer(message_id: int, user_id: int) -> dict:
    row = db.fetch_one(
        """SELECT m.* FROM messages m JOIN conversations c ON c.id = m.conversation_id
           WHERE m.id = %s AND c.user_id = %s AND m.role = 'assistant'""",
        (message_id, user_id),
    )
    if not row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Yanıt bulunamadı")
    return row


@router.put("/messages/{message_id}/save", status_code=status.HTTP_204_NO_CONTENT, summary="Yanıtı kaydet")
def save_answer(message_id: int, user: dict = Depends(get_current_user)):
    _own_answer(message_id, user["id"])
    db.execute("UPDATE messages SET saved_at = COALESCE(saved_at, now()) WHERE id = %s", (message_id,))


@router.delete("/messages/{message_id}/save", status_code=status.HTTP_204_NO_CONTENT, summary="Yanıt kaydını kaldır")
def unsave_answer(message_id: int, user: dict = Depends(get_current_user)):
    _own_answer(message_id, user["id"])
    db.execute("UPDATE messages SET saved_at = NULL WHERE id = %s", (message_id,))


@router.get("/saved/answers", response_model=list[SavedAnswerOut], summary="Kaydedilen yanıtlar")
def saved_answers(q: str | None = Query(None, max_length=100), user: dict = Depends(get_current_user)):
    params: dict = {"u": user["id"]}
    extra = ""
    if q and q.strip():
        extra = "AND (m.content ILIKE %(q)s OR qm.content ILIKE %(q)s)"
        params["q"] = f"%{q.strip()}%"
    rows = db.fetch_all(
        f"""SELECT m.id AS message_id, m.conversation_id, m.content, m.citations, m.saved_at,
                   COALESCE(qm.content, c.title) AS question
            FROM messages m
            JOIN conversations c ON c.id = m.conversation_id
            LEFT JOIN LATERAL (
                SELECT content FROM messages u WHERE u.conversation_id = m.conversation_id AND u.role = 'user' AND u.id < m.id
                ORDER BY u.id DESC LIMIT 1) qm ON true
            WHERE c.user_id = %(u)s AND m.saved_at IS NOT NULL {extra}
            ORDER BY m.saved_at DESC""",
        params,
    )
    out = []
    for r in rows:
        text = " ".join(r["content"].replace("**", "").split())
        out.append({
            "message_id": r["message_id"],
            "conversation_id": r["conversation_id"],
            "question": r["question"],
            "snippet": text[:220] + ("…" if len(text) > 220 else ""),
            "sources": _sources_of(r["citations"])[:3],
            "source_count": len(r["citations"] or []),
            "saved_at": r["saved_at"],
        })
    return out
