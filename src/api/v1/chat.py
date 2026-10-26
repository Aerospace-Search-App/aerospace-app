"""Sohbet uçları (`/api/v1/chat`): kaynak gösteren soru-cevap ve kullanıcının sohbet geçmişi."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from src.api.responses import errors
from src.application.schemas.chat import ChatAnswerOut, ChatAskRequest, ConversationDetailOut, ConversationOut
from src.application.schemas.common import Page, PageParams, to_page
from src.application.services.chat_service import ChatService
from src.core.deps import get_chat_service, get_current_user
from src.domain.entities import User

router = APIRouter(prefix="/chat", tags=["Search & Chat"])

Service = Annotated[ChatService, Depends(get_chat_service)]
CurrentUser = Annotated[User, Depends(get_current_user)]
_NOT_FOUND = {404: "Sohbet bulunamadı veya size ait değil (NOT_FOUND)."}


@router.post(
    "/ask",
    response_model=ChatAnswerOut,
    status_code=200,
    summary="Soru sor (kaynaklı cevap)",
    description="Soruyu seçili standartlarda arar ve kaynak gösteren bir cevap üretir. `conversation_id` null ise "
                "yeni sohbet açılır. Her zaman 200 döner; sonucu `status` söyler: `ANSWERED`, `NO_RESULTS` "
                "(kaynak yok, `answer` null) veya `LLM_UNAVAILABLE` (kaynaklar var, `answer` null).",
    responses=errors(_NOT_FOUND, auth=True),
)
def ask(body: ChatAskRequest, user: CurrentUser, svc: Service) -> ChatAnswerOut:
    # TODO(Onur): web arayüzündeki sohbet de bu uca bağlanacak. TODO(Sudenur): arama + kaynaklı cevap kalitesi.
    result = svc.ask(user, body.question, body.standard_ids, body.conversation_id, body.top_k)
    return ChatAnswerOut.model_validate(result)


@router.get(
    "/conversations",
    response_model=Page[ConversationOut],
    status_code=200,
    summary="Sohbetlerim",
    description="Kullanıcının sohbetlerini en yeniden eskiye, sayfalı döner. `title` ilk sorunun ilk 60 karakteridir.",
    responses=errors(auth=True),
)
def list_conversations(user: CurrentUser, svc: Service,
                       paging: Annotated[PageParams, Query()]) -> Page[ConversationOut]:
    items, total = svc.list_conversations(user, offset=paging.offset, limit=paging.page_size)
    return to_page(ConversationOut, items, total, paging)


@router.get(
    "/conversations/{conversation_id}",
    response_model=ConversationDetailOut,
    status_code=200,
    summary="Sohbet detayı",
    description="Sohbeti tüm mesajları ve kaynaklarıyla (eskiden yeniye) döner. Başkasının sohbeti 404 döner.",
    responses=errors(_NOT_FOUND, auth=True),
)
def get_conversation(conversation_id: int, user: CurrentUser, svc: Service) -> ConversationDetailOut:
    return ConversationDetailOut.model_validate(svc.get_conversation(user, conversation_id))
