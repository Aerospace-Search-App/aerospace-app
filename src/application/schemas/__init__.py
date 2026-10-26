"""Pydantic istek/cevap şemaları: mobil ekibin göreceği API sözleşmesi.

Kural: istek şemaları (`...Request`, `...Create`) istemciden gelen veriyi sınırlarıyla doğrular; cevap şemaları
(`...Out`, `...Response`) sunucunun döndürdüğü şekli tanımlar. Router'lar buradan import eder.
"""

from src.application.schemas.auth import LoginRequest, RefreshRequest, RegisterRequest, TokenResponse, UserOut
from src.application.schemas.chat import (
    ChatAnswerOut,
    ChatAskRequest,
    ConversationDetailOut,
    ConversationOut,
    MessageOut,
)
from src.application.schemas.common import ErrorDetail, ErrorResponse, Page, PageParams
from src.application.schemas.meta import EnumsOut, Limits, VerdictOption
from src.application.schemas.report import AnalysisCreate, AnalysisOut, ReportOut
from src.application.schemas.search import SearchRequest, SearchResponse, SourceOut
from src.application.schemas.standard import IndexStatusOut, StandardCreate, StandardOut
from src.application.schemas.system import HealthChecks, HealthOut, RootOut

__all__ = [
    "AnalysisCreate", "AnalysisOut",
    "ChatAnswerOut", "ChatAskRequest", "ConversationDetailOut", "ConversationOut", "MessageOut",
    "EnumsOut", "Limits", "VerdictOption",
    "ErrorDetail", "ErrorResponse", "Page", "PageParams",
    "HealthChecks", "HealthOut", "RootOut",
    "IndexStatusOut", "StandardCreate", "StandardOut",
    "LoginRequest", "RefreshRequest", "RegisterRequest", "TokenResponse", "UserOut",
    "ReportOut",
    "SearchRequest", "SearchResponse", "SourceOut",
]
