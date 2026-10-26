"""Sohbet şemaları (sözleşme §5) — `POST /chat/ask`, `GET /chat/conversations`, `GET /chat/conversations/{id}`.

Cevabın `status` alanı üç durumu ayırır (hepsi HTTP 200):
- `ANSWERED`: cevap üretildi, `answer` dolu, `sources` dolu.
- `NO_RESULTS`: arama hiçbir parça bulamadı → `answer = null`, `sources = []`.
- `LLM_UNAVAILABLE`: parçalar bulundu ama dil modeli cevap üretemedi → `answer = null`, `sources` dolu.
Eski kod LLM hatasında ham metni `answer`'a basıyordu; artık yapılmaz (mobil `status`'a bakar).
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from src.application.schemas.search import DEFAULT_TOP_K, MAX_TOP_K, SOURCE_EXAMPLE, SourceOut
from src.domain.enums import ChatStatus

_QUESTION = "Vibrasyon testi kaç saat sürmeli?"
_ANSWER = (
    "[DEMO] MIL-STD-810H Method 514.8'e göre titreşim testi, ilgili tablodaki profil için her eksende "
    "en az 1 saat uygulanır (Sayfa 412)."
)
_SOURCE = SOURCE_EXAMPLE
_MESSAGE_EXAMPLE = {
    "id": 31, "question": _QUESTION, "answer": _ANSWER, "status": "ANSWERED",
    "sources": [_SOURCE], "created_at": "2026-10-26T09:40:00Z",
}
_CONVERSATION_EXAMPLE = {
    "id": 5, "title": _QUESTION, "message_count": 1, "standard_ids": [1],
    "created_at": "2026-10-26T09:40:00Z", "updated_at": "2026-10-26T09:40:00Z",
}

_ANSWER_DESCRIPTION = (
    "Kaynak gösteren cevap. `status` NO_RESULTS veya LLM_UNAVAILABLE ise `null` olur."
)


class ChatAskRequest(BaseModel):
    """`POST /api/v1/chat/ask` gövdesi. `conversation_id = null` → yeni sohbet; doluysa o sohbete eklenir."""

    model_config = ConfigDict(str_strip_whitespace=True, json_schema_extra={"examples": [
        {"question": _QUESTION, "standard_ids": [1], "conversation_id": None, "top_k": 5},
    ]})

    question: str = Field(..., min_length=3, max_length=2000, description="Soru (3–2000 karakter).",
                          examples=[_QUESTION])
    standard_ids: list[int] = Field(default_factory=list,
                                    description="Sorunun sorulacağı standartlar. Boş liste = tümü.",
                                    examples=[[1]])
    conversation_id: int | None = Field(default=None,
                                        description="Devam edilecek sohbet; null ise yeni sohbet açılır.",
                                        examples=[None])
    top_k: int = Field(default=DEFAULT_TOP_K, ge=1, le=MAX_TOP_K,
                       description="Cevap için kullanılacak kaynak parça sayısı (1–20).", examples=[5])


class ChatAnswerOut(BaseModel):
    """`POST /chat/ask` cevabı: cevap + kaynaklar + durum. Durum ne olursa olsun HTTP 200 döner."""

    model_config = ConfigDict(from_attributes=True, json_schema_extra={"examples": [
        {
            "conversation_id": 5, "message_id": 31, "question": _QUESTION, "answer": _ANSWER,
            "status": "ANSWERED", "sources": [_SOURCE], "model": "gemini-2.5-flash", "duration_ms": 1830,
            "created_at": "2026-10-26T09:40:00Z",
        },
        {
            "conversation_id": 5, "message_id": 32, "question": "Uçuş kontrol yazılımı için DAL-A nedir?",
            "answer": None, "status": "NO_RESULTS", "sources": [], "model": "gemini-2.5-flash",
            "duration_ms": 35, "created_at": "2026-10-26T09:41:00Z",
        },
    ]})

    conversation_id: int = Field(..., description="Mesajın ait olduğu sohbet.", examples=[5])
    message_id: int = Field(..., description="Bu soru-cevap mesajının kimliği.", examples=[31])
    question: str = Field(..., description="Sorulan soru.", examples=[_QUESTION])
    answer: str | None = Field(default=None, description=_ANSWER_DESCRIPTION, examples=[_ANSWER])
    status: ChatStatus = Field(..., description="ANSWERED, NO_RESULTS veya LLM_UNAVAILABLE.",
                               examples=["ANSWERED"])
    sources: list[SourceOut] = Field(default_factory=list,
                                     description="Cevabın dayandığı parçalar (NO_RESULTS'ta boş).",
                                     examples=[[_SOURCE]])
    model: str = Field(..., description="Cevabı üreten model adı.", examples=["gemini-2.5-flash"])
    duration_ms: int = Field(..., ge=0, description="Toplam süre (milisaniye).", examples=[1830])
    created_at: datetime = Field(..., description="Mesaj zamanı (UTC).", examples=["2026-10-26T09:40:00Z"])


class MessageOut(BaseModel):
    """Sohbet geçmişindeki bir soru-cevap mesajı."""

    model_config = ConfigDict(from_attributes=True, json_schema_extra={"examples": [_MESSAGE_EXAMPLE]})

    id: int = Field(..., description="Mesaj kimliği.", examples=[31])
    question: str = Field(..., description="Sorulan soru.", examples=[_QUESTION])
    answer: str | None = Field(default=None, description=_ANSWER_DESCRIPTION, examples=[_ANSWER])
    status: ChatStatus = Field(..., description="Cevap durumu.", examples=["ANSWERED"])
    sources: list[SourceOut] = Field(default_factory=list, description="Kaynak parçalar.", examples=[[_SOURCE]])
    created_at: datetime = Field(..., description="Mesaj zamanı (UTC).", examples=["2026-10-26T09:40:00Z"])


class ConversationOut(BaseModel):
    """Sohbet listesindeki satır. `title` = ilk sorunun ilk 60 karakteri."""

    model_config = ConfigDict(from_attributes=True, json_schema_extra={"examples": [_CONVERSATION_EXAMPLE]})

    id: int = Field(..., description="Sohbet kimliği.", examples=[5])
    title: str = Field(..., description="İlk sorunun ilk 60 karakteri.", examples=[_QUESTION])
    message_count: int = Field(..., ge=0, description="Sohbetteki mesaj sayısı.", examples=[1])
    standard_ids: list[int] = Field(default_factory=list, description="Sohbette kullanılan standartlar.",
                                    examples=[[1]])
    created_at: datetime = Field(..., description="Sohbetin açıldığı zaman (UTC).",
                                 examples=["2026-10-26T09:40:00Z"])
    updated_at: datetime = Field(..., description="Son mesaj zamanı (UTC).", examples=["2026-10-26T09:40:00Z"])


class ConversationDetailOut(ConversationOut):
    """Sohbet detayı: `ConversationOut` alanları + eskiden yeniye mesajlar."""

    model_config = ConfigDict(from_attributes=True, json_schema_extra={"examples": [
        {**_CONVERSATION_EXAMPLE, "messages": [_MESSAGE_EXAMPLE]},
    ]})

    messages: list[MessageOut] = Field(default_factory=list, description="Mesajlar (eskiden yeniye).",
                                       examples=[[_MESSAGE_EXAMPLE]])
