"""Sohbet servisi: kaynak gösteren soru-cevap (RAG) ve sohbet geçmişi.

Akış (`ask`): sohbeti bul/aç → `RetrievalService` ile ilgili parçaları bul → `LLMClient` ile cevap üret → mesajı kaydet.
Üç sonuç (hepsi HTTP 200, mobil `status`'a bakar):
- parça yok → `NO_RESULTS`, `answer = null`, `sources = []` (LLM hiç çağrılmaz),
- LLM hata verdi → `LLM_UNAVAILABLE`, `answer = null`, `sources` dolu (eski kod burada ham metni cevaba basıyordu),
- aksi halde `ANSWERED`.

Sohbetler kullanıcıya özeldir: başkasının sohbeti "yok" sayılır (404) ki varlığı sızmasın.
TODO(Onur): web arayüzündeki sohbet ekranı da bu servisi (`POST /api/v1/chat/ask`) kullanacak.
"""

import time
from dataclasses import dataclass
from datetime import datetime

from loguru import logger

from src.application.services.retrieval_service import RetrievalService
from src.core.errors import NotFoundError
from src.domain.entities import Conversation, Message, Source, User, utc_now
from src.domain.enums import ChatStatus, SearchMode
from src.domain.interfaces import ConversationRepository, LLMClient, LLMError

TITLE_MAX_LENGTH = 60


@dataclass(frozen=True, slots=True)
class ChatAnswer:
    """`POST /chat/ask` sonucu (`ChatAnswerOut` şemasına birebir dönüşür)."""

    conversation_id: int
    message_id: int
    question: str
    answer: str | None
    status: ChatStatus
    sources: list[Source]
    model: str
    duration_ms: int
    created_at: datetime


class ChatService:
    """Soru-cevap ve sohbet geçmişi iş kuralları."""

    def __init__(self, conversations: ConversationRepository, retrieval: RetrievalService, llm: LLMClient) -> None:
        self._conversations = conversations
        self._retrieval = retrieval
        self._llm = llm

    def ask(self, user: User, question: str, standard_ids: list[int], conversation_id: int | None,
            top_k: int) -> ChatAnswer:
        started = time.perf_counter()
        conversation = (self.get_conversation(user, conversation_id) if conversation_id is not None
                        else self._open_conversation(user, question))
        sources = self._retrieval.search(question, standard_ids, top_k, SearchMode.HYBRID).results
        answer, status = self._generate(question, sources)
        # Aramada olmayan id'ler sessizce atlanır; sohbet kaydına da sadece var olan standartlar yazılır.
        known = self._retrieval.existing_standard_ids(standard_ids)
        conversation.standard_ids = sorted(set(conversation.standard_ids) | set(known))
        message = self._conversations.add_message(conversation, Message(
            conversation_id=conversation.id, question=question, answer=answer, status=status, sources=sources,
            model=self._llm.model_name, duration_ms=int((time.perf_counter() - started) * 1000),
        ))
        return ChatAnswer(
            conversation_id=conversation.id, message_id=message.id, question=question, answer=answer,
            status=status, sources=sources, model=message.model, duration_ms=message.duration_ms,
            created_at=message.created_at,
        )

    def list_conversations(self, user: User, *, offset: int, limit: int) -> tuple[list[Conversation], int]:
        return self._conversations.list_by_user(user.id, offset=offset, limit=limit)

    def get_conversation(self, user: User, conversation_id: int) -> Conversation:
        conversation = self._conversations.get(conversation_id)
        if conversation is None or conversation.user_id != user.id:
            raise NotFoundError(f"Sohbet bulunamadı: id={conversation_id}")
        return conversation

    def _open_conversation(self, user: User, question: str) -> Conversation:
        now = utc_now()
        title = question.strip()[:TITLE_MAX_LENGTH]
        return self._conversations.add(Conversation(user_id=user.id, title=title, created_at=now, updated_at=now))

    def _generate(self, question: str, sources: list[Source]) -> tuple[str | None, ChatStatus]:
        if not sources:
            return None, ChatStatus.NO_RESULTS
        try:
            return self._llm.answer(question, sources), ChatStatus.ANSWERED
        except LLMError as exc:
            logger.warning("LLM cevap üretemedi: {}", exc)
            return None, ChatStatus.LLM_UNAVAILABLE
