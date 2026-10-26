"""API istek/yanıt modelleri (Swagger'da görünür)."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field, field_validator


# --- Kimlik doğrulama -----------------------------------------------------
USERNAME_RE = r"^[a-zA-Z0-9._-]{3,30}$"


class RegisterIn(BaseModel):
    username: str = Field(min_length=3, max_length=30, pattern=USERNAME_RE, examples=["halil.turan"])
    email: EmailStr = Field(examples=["halil@example.com"])
    password: str = Field(min_length=8, max_length=128, examples=["GucluParola123"])
    full_name: str = Field(default="", max_length=120, examples=["Halil Turan"])
    organization: str | None = Field(default=None, max_length=120)
    accept_terms: bool = Field(default=False, validate_default=True, description="KVKK ve kullanım koşulları onayı")

    @field_validator("accept_terms")
    @classmethod
    def terms(cls, v: bool) -> bool:
        if not v:
            raise ValueError("KVKK ve kullanım koşullarını kabul etmelisiniz")
        return v

    @field_validator("password")
    @classmethod
    def strong(cls, v: str) -> str:
        if not any(c.isdigit() for c in v) or not any(c.isalpha() for c in v):
            raise ValueError("Parola en az bir harf ve bir rakam içermeli")
        return v


class LoginIn(BaseModel):
    email: str = Field(min_length=3, max_length=254, examples=["halil@example.com"])
    password: str = Field(min_length=1, max_length=128)


class MeUpdate(BaseModel):
    username: str | None = Field(default=None, min_length=3, max_length=30, pattern=USERNAME_RE)
    full_name: str | None = Field(default=None, max_length=120)
    organization: str | None = Field(default=None, max_length=120)


class UserOut(BaseModel):
    id: int
    email: str
    username: str | None = None
    full_name: str
    role: str
    organization: str | None = None
    created_at: datetime


class TokenOut(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    user: UserOut


# --- Dokümanlar -----------------------------------------------------------
class DocumentOut(BaseModel):
    id: int
    code: str
    title: str
    issuer: str
    category: str
    domains: list[str]
    language: str
    version: str
    published_on: str
    summary: str
    source_url: str
    page_count: int
    chunk_count: int
    embedded_count: int
    status: str
    error: str | None = None
    created_at: datetime
    is_saved: bool = False


class DocumentUpdate(BaseModel):
    code: str | None = None
    title: str | None = None
    issuer: str | None = None
    category: Literal["civil", "defense"] | None = None
    domains: list[str] | None = None
    language: Literal["en", "tr"] | None = None
    version: str | None = None
    published_on: str | None = None
    summary: str | None = None


class ChunkOut(BaseModel):
    id: int
    document_id: int
    ord: int
    clause_ref: str
    heading: str
    heading_path: str
    part: int
    page_start: int
    page_end: int
    content: str


class ClauseListItem(BaseModel):
    id: int
    ord: int
    clause_ref: str
    heading: str
    page_start: int
    part: int


class SourceOut(BaseModel):
    chunk: ChunkOut
    document: DocumentOut
    prev_id: int | None
    next_id: int | None
    is_saved: bool
    file_url: str          # PDF (göreli URL, kısa ömürlü token içerir)
    page_image_url: str    # maddenin bulunduğu sayfanın vurgulu PNG görüntüsü


# --- Arama ----------------------------------------------------------------
class SearchIn(BaseModel):
    query: str = Field(min_length=2, max_length=1000, examples=["Yazılım seviyesi A için hangi hedefler gerekir?"])
    k: int = Field(default=8, ge=1, le=30)
    document_ids: list[int] | None = None
    category: Literal["civil", "defense"] | None = None
    project_id: int | None = None


class SearchHit(BaseModel):
    chunk_id: int
    document_id: int
    code: str
    doc_title: str
    clause_ref: str
    heading: str
    page_start: int
    page_end: int
    snippet: str
    score: float
    lexical_rank: int | None = None
    vector_rank: int | None = None


class SearchOut(BaseModel):
    query: str
    expanded_terms: list[str]
    mode: str
    hits: list[SearchHit]


# --- Sohbet ---------------------------------------------------------------
class Citation(BaseModel):
    n: int
    chunk_id: int
    document_id: int
    code: str
    issuer: str = ""
    version: str = ""
    doc_title: str
    clause_ref: str
    heading: str
    page_start: int
    snippet: str


class ChatIn(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    conversation_id: int | None = None
    project_id: int | None = None
    category: Literal["civil", "defense"] | None = None
    issuer: str | None = Field(default=None, max_length=40, description="Kaynak filtresi: FAA, SHGM, DoD ...")


class MessageOut(BaseModel):
    id: int
    role: str
    content: str
    citations: list[Citation] = []
    meta: dict = {}
    saved: bool = False
    created_at: datetime


class ChatOut(BaseModel):
    conversation_id: int
    title: str
    user_message: MessageOut
    answer: MessageOut


class ConversationOut(BaseModel):
    id: int
    title: str
    project_id: int | None
    project_name: str | None = None
    created_at: datetime
    updated_at: datetime
    last_message: str | None = None
    message_count: int = 0
    starred: bool = False
    sources: list[str] = []


class ConversationDetail(ConversationOut):
    messages: list[MessageOut]


# --- Projeler -------------------------------------------------------------
class ProjectIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    description: str = Field(default="", max_length=2000)
    category: Literal["civil", "defense", "both"] = "civil"
    domains: list[str] = []


class ProjectOut(BaseModel):
    id: int
    name: str
    description: str
    category: str
    domains: list[str]
    created_at: datetime
    updated_at: datetime
    saved_count: int = 0
    conversation_count: int = 0


class RecommendedClause(BaseModel):
    chunk_id: int
    clause_ref: str
    heading: str
    page_start: int
    snippet: str


class Recommendation(BaseModel):
    document: DocumentOut
    score: float
    reasons: list[str]
    clauses: list[RecommendedClause]


# --- Kaydedilenler --------------------------------------------------------
class SavedIn(BaseModel):
    document_id: int
    chunk_id: int | None = None
    project_id: int | None = None
    note: str = Field(default="", max_length=1000)


class SavedOut(BaseModel):
    id: int
    document_id: int
    chunk_id: int | None
    project_id: int | None
    note: str
    created_at: datetime
    code: str
    doc_title: str
    issuer: str
    category: str
    clause_ref: str | None = None
    heading: str | None = None
    page_start: int | None = None
    snippet: str | None = None


class SavedAnswerOut(BaseModel):
    message_id: int
    conversation_id: int
    question: str
    snippet: str
    sources: list[str]
    source_count: int
    saved_at: datetime


class IssuerOut(BaseModel):
    issuer: str
    documents: int
