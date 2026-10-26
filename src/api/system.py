"""Sistem endpoint'leri: `GET /` ve `GET /health` (prefix'siz, auth istemez).

Mobil uygulama açılışta `/health`'i çağırıp sunucunun ayakta olduğunu ve hangi modda (mock/gerçek)
çalıştığını görür.
"""

from fastapi import APIRouter, Depends

from src.application.schemas.common import ErrorResponse
from src.application.schemas.system import HealthChecks, HealthOut, RootOut
from src.core.config import Settings, get_settings

router = APIRouter(tags=["System"])


@router.get(
    "/",
    response_model=RootOut,
    status_code=200,
    summary="Uygulama bilgisi",
    description="Uygulamanın adı, sürümü, Swagger adresi ve API taban yolunu döner.",
    responses={500: {"model": ErrorResponse, "description": "Beklenmeyen hata"}},
)
def root(settings: Settings = Depends(get_settings)) -> RootOut:
    return RootOut(app=settings.APP_NAME, version=settings.APP_VERSION, docs="/docs", api=settings.API_V1_PREFIX)


@router.get(
    "/health",
    response_model=HealthOut,
    status_code=200,
    summary="Sağlık kontrolü",
    description="Sunucunun ve bileşenlerinin (veritabanı, arama, LLM) durumunu döner. Sorun olsa da 200 döner; "
                "durum `status` alanındadır.",
    responses={500: {"model": ErrorResponse, "description": "Beklenmeyen hata"}},
)
def health(settings: Settings = Depends(get_settings)) -> HealthOut:
    # Sözleşme §2: bir bileşen çalışmıyorsa status="degraded" ve ilgili check "error" olur (HTTP yine 200).
    # Bu hafta her şey bellek-içi mock olduğundan hep "ok". TODO(Doruk): gerçek DB'ye ping atılınca burası
    # bileşenlerin kendi kontrolünü çağıracak (ör. app.state.db.ping()).
    checks = HealthChecks(database="ok", search=settings.SEARCH_PROVIDER, llm=settings.LLM_PROVIDER)
    return HealthOut(status="ok", version=settings.APP_VERSION, checks=checks)
