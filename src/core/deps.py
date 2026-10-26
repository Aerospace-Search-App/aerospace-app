"""Dependency'ler ve **takma noktaları**: hangi implementasyonun (mock mu, gerçek mi) kullanılacağı SADECE burada seçilir.

Bu dosya projenin ana mesajıdır:
- `init_app_state` uygulama açılırken (lifespan) **bir kez** çalışır: repository'leri, arama motorunu, dil modelini
  ve dosya deposunu oluşturur, seed verisini yükler ve hepsini `app.state`'e koyar (istek başına yeniden yaratılmaz).
- `get_*_service` fonksiyonları her istekte bu hazır nesnelerden hafif bir servis kurar; router `Depends(...)` ile ister.
- Servisler somut sınıfları değil arayüzleri (`src/domain/interfaces.py`) tanır.

Benzetme: Bir sigorta kutusu. Hangi hattın hangi cihaza (mock / PostgreSQL / Gemini) bağlı olduğu tek panoda
yazılıdır; ekip arkadaşı gerçeğini getirince sadece bu panoda bir satır değişir, duvarlar (router/servis) kırılmaz.

Takma noktaları:
- TODO(Doruk): `InMemory*Repository` → PostgreSQL repository'leri.
- TODO(Sudenur): `SEARCH_PROVIDER` → hibrit arama implementasyonu.
- TODO: `LLM_PROVIDER=gemini` → Gemini istemcisi (şimdilik "bağlanmadı" yer tutucusu; sohbet LLM_UNAVAILABLE döner).
- TODO(Taha): `get_current_user` içinde gerçek JWT doğrulaması.
"""

from fastapi import Depends, FastAPI, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from loguru import logger

from src.application.services.analysis_service import AnalysisService
from src.application.services.auth_service import AuthService
from src.application.services.chat_service import ChatService
from src.application.services.report_service import ReportService
from src.application.services.retrieval_service import RetrievalService
from src.application.services.standards_service import StandardsService
from src.core.config import Settings, get_settings
from src.core.errors import ForbiddenError, UnauthorizedError
from src.domain.entities import User
from src.domain.enums import UserRole
from src.domain.interfaces import LLMClient
from src.infrastructure.llm.mock_llm import MockLLMClient, UnavailableLLMClient
from src.infrastructure.memory.repositories import (
    InMemoryAnalysisRepository,
    InMemoryConversationRepository,
    InMemoryReportRepository,
    InMemoryStandardRepository,
    InMemoryUserRepository,
)
from src.infrastructure.memory.seed import DEMO_USER, seed_all
from src.infrastructure.search.mock_search import MockSearchService
from src.infrastructure.storage.local_storage import LocalFileStorage

__all__ = [
    "DEMO_USER", "bearer_scheme", "get_analysis_service", "get_auth_service", "get_chat_service",
    "get_current_user", "get_report_service", "get_retrieval_service", "get_settings", "get_standards_service",
    "init_app_state", "require_admin",
]

# Swagger'daki "Authorize" butonunun şeması. auto_error=False: token yoksa FastAPI kendi 403'ünü atmasın,
# karar get_current_user'da verilsin ve hata tek tip formatta (401 UNAUTHORIZED) dönsün.
bearer_scheme = HTTPBearer(auto_error=False, description="Giriş (`/auth/login`) sonrası alınan access token.")


# --------------------------------------------------------------------------------------------- kurulum (lifespan)


def _build_llm(settings: Settings) -> LLMClient:
    if settings.LLM_PROVIDER == "mock":
        return MockLLMClient()
    # TODO: "gemini" → GeminiLLMClient(api_key=settings.GEMINI_API_KEY, model=settings.GEMINI_MODEL)
    logger.warning("LLM_PROVIDER={} henüz bağlanmadı; LLM çağrıları LLM_UNAVAILABLE dönecek.", settings.LLM_PROVIDER)
    return UnavailableLLMClient(settings.LLM_PROVIDER)


def init_app_state(app: FastAPI, settings: Settings) -> None:
    """Paylaşılan nesneleri bir kez oluşturur, seed eder ve `app.state`'e koyar (lifespan'den çağrılır)."""
    if settings.SEARCH_PROVIDER != "mock":
        # TODO(Sudenur): "hybrid" → HybridSearchService(...) burada seçilecek.
        raise RuntimeError(f"Desteklenmeyen SEARCH_PROVIDER: {settings.SEARCH_PROVIDER!r}. "
                           "Şimdilik sadece 'mock' kullanılabilir.")
    storage = LocalFileStorage(settings.STORAGE_DIR, settings.MAX_UPLOAD_MB)
    search = MockSearchService(page_counter=storage.count_pages)
    state = app.state
    state.storage = storage
    state.search = search
    state.llm = _build_llm(settings)
    # TODO(Doruk): PostgreSQL repository'leri burada oluşturulacak (bağlantı havuzu da lifespan'de).
    state.standard_repo = InMemoryStandardRepository()
    state.conversation_repo = InMemoryConversationRepository()
    state.report_repo = InMemoryReportRepository()
    state.analysis_repo = InMemoryAnalysisRepository()
    state.user_repo = InMemoryUserRepository()
    seed_all(state.standard_repo, state.report_repo, state.user_repo, search)


# --------------------------------------------------------------------------------------------- servis sağlayıcıları


def get_standards_service(request: Request) -> StandardsService:
    s = request.app.state
    return StandardsService(s.standard_repo, s.search, s.storage)


def get_retrieval_service(request: Request) -> RetrievalService:
    s = request.app.state
    return RetrievalService(s.standard_repo, s.search)


def get_chat_service(request: Request) -> ChatService:
    s = request.app.state
    return ChatService(s.conversation_repo, get_retrieval_service(request), s.llm)


def get_report_service(request: Request) -> ReportService:
    s = request.app.state
    return ReportService(s.report_repo, s.storage)


def get_analysis_service(request: Request) -> AnalysisService:
    s = request.app.state
    return AnalysisService(s.analysis_repo, s.report_repo, get_report_service(request),
                           get_retrieval_service(request), s.llm)


def get_auth_service(request: Request) -> AuthService:
    return AuthService(request.app.state.user_repo)


# --------------------------------------------------------------------------------------------- kimlik


def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    settings: Settings = Depends(get_settings),
) -> User:
    """İsteği yapan kullanıcıyı döner.

    - `AUTH_ENABLED=false` (bu hafta): token'a bakmadan demo kullanıcı (id=1, ADMIN).
    - `AUTH_ENABLED=true`: token yoksa veya geçersizse 401. Şimdilik sadece stub token'lar (`/auth/login`
      cevabındaki `stub-access...`) kabul edilir.
    """
    if not settings.AUTH_ENABLED:
        return DEMO_USER
    if credentials is None:
        raise UnauthorizedError("Kimlik doğrulaması gerekli: Authorization: Bearer <token> başlığı eksik.")
    # TODO(Taha): JWT doğrulama — src/core/security.py ile token'ı çöz, süresini kontrol et.
    user = get_auth_service(request).user_from_access_token(credentials.credentials)
    if user is None:
        raise UnauthorizedError("Token geçersiz veya süresi dolmuş.")
    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    """Sadece ADMIN rolüne izin verir (sözleşmedeki 🔒A uçları). Demo kullanıcı ADMIN'dir."""
    if user.role != UserRole.ADMIN:
        raise ForbiddenError("Bu işlem için yönetici (ADMIN) yetkisi gerekli.")
    return user
