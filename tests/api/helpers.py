"""Faz 3/4 testlerinin ortak yardımcıları (hata formatı, UTC tarih, kullanıcı değiştirme, yükleme)."""

import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from fastapi import FastAPI

from src.core.deps import get_current_user
from src.domain.entities import User
from src.domain.enums import UserRole

UUID_PDF_NAME = re.compile(r"^[0-9a-f]{32}\.pdf$")

SOURCE_KEYS = {"chunk_id", "standard_id", "standard_code", "requirement_id", "section", "page", "snippet", "score"}
STANDARD_KEYS = {
    "id", "code", "title", "standard_type", "version", "issuing_body", "publication_year", "description",
    "status", "index_status", "is_indexed", "has_document", "page_count", "chunk_count", "requirement_count",
    "indexed_at", "created_at", "updated_at",
}
INDEX_STATUS_KEYS = {"standard_id", "index_status", "progress", "page_count", "chunk_count", "error_message",
                     "started_at", "finished_at"}
PAGE_KEYS = {"items", "total", "page", "page_size"}
REPORT_KEYS = {"id", "title", "original_filename", "report_type", "status", "file_size_kb", "page_count",
               "analysis_count", "error_message", "uploaded_at", "processed_at"}
ANALYSIS_KEYS = {"id", "report_id", "query", "verdict", "verdict_label", "confidence", "is_high_confidence",
                 "reasoning", "sources", "model", "duration_ms", "created_at"}
CHAT_ANSWER_KEYS = {"conversation_id", "message_id", "question", "answer", "status", "sources", "model",
                    "duration_ms", "created_at"}
CONVERSATION_KEYS = {"id", "title", "message_count", "standard_ids", "created_at", "updated_at"}
MESSAGE_KEYS = {"id", "question", "answer", "status", "sources", "created_at"}
USER_KEYS = {"id", "email", "full_name", "created_at"}  # Taha'nın şekli: role yok
TOKEN_KEYS = {"access_token", "refresh_token", "token_type", "expires_in"}  # Taha'nın şekli: user yok

ENGINEER = User(id=2, email="muhendis@aerospace.local", full_name="Mühendis Kullanıcı", role=UserRole.ENGINEER)
OTHER_ADMIN = User(id=99, email="baska@aerospace.local", full_name="Başka Kullanıcı", role=UserRole.ADMIN)


def assert_error_shape(response, status: int, code: str) -> dict[str, Any]:
    """Sözleşme §0: `{"error": {"code", "message", "details"}}`; başka anahtar ve stack trace yok."""
    assert response.status_code == status, response.text
    assert response.headers["content-type"].startswith("application/json")
    body = response.json()
    assert set(body.keys()) == {"error"}, body
    err = body["error"]
    assert set(err.keys()) == {"code", "message", "details"}, err
    assert err["code"] == code, err
    assert isinstance(err["message"], str) and err["message"].strip()
    for marker in ("Traceback", 'File "', "Exception", "Error(", "\\src\\", "/src/"):
        assert marker not in response.text, (marker, response.text)
    return err


def assert_utc(value: Any) -> datetime:
    """ISO 8601 ve UTC (sonu `Z` veya `+00:00`; naive değil)."""
    assert isinstance(value, str), value
    assert value.endswith("Z") or value.endswith("+00:00"), value
    parsed = datetime.fromisoformat(value)
    assert parsed.tzinfo is not None and parsed.utcoffset() == timedelta(0), value
    return parsed


def assert_source(src: dict[str, Any]) -> None:
    assert set(src.keys()) == SOURCE_KEYS, src
    assert isinstance(src["chunk_id"], str) and src["chunk_id"]
    assert isinstance(src["standard_id"], int)
    assert isinstance(src["standard_code"], str) and src["standard_code"]
    assert isinstance(src["snippet"], str) and src["snippet"]
    assert 0.0 <= src["score"] <= 1.0
    assert src["page"] is None or src["page"] >= 1


def act_as(app: FastAPI, user: User) -> None:
    """İsteği yapan kullanıcıyı değiştirir (`get_current_user` override; `require_admin` da bunu kullanır)."""
    app.dependency_overrides[get_current_user] = lambda: user


def stored_files(storage_dir: Path) -> list[Path]:
    """Depoya yazılmış dosyalar (klasör hiç oluşmadıysa boş liste)."""
    if not storage_dir.exists():
        return []
    return [p for p in storage_dir.rglob("*") if p.is_file()]


def pdf_upload(content: bytes, filename: str = "belge.pdf", content_type: str = "application/pdf"):
    return {"file": (filename, content, content_type)}
