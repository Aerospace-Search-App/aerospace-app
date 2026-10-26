"""Uygulamanın giriş noktası: `uvicorn main:app`.

`create_app()` bir "fabrika" fonksiyonudur: uygulamayı her çağrıldığında sıfırdan, aynı adımlarla kurar
(ayarlar → hata handler'ları → CORS → router'lar → Swagger ayarları). Testler de kendi temiz
uygulamalarını bu fonksiyonla üretebilir.
"""

import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from loguru import logger

from src.api import auth, system
from src.api.v1 import api_v1_router
from src.application.schemas.common import ErrorResponse
from src.core.config import get_settings
from src.core.deps import init_app_state
from src.core.errors import register_exception_handlers
from src.core.logging import setup_logging

API_DESCRIPTION = """
Havacılık/savunma standartlarına (MIL-STD-810H, MIL-STD-461G, DO-178C) **RAG ile soru-cevap** ve teknik rapor
**uyumluluk analizi** yapan platformun mobil uygulamaya hizmet veren API'si.

**Mock mod:** Bu sürümde veritabanı, vektör arama ve LLM yerine bellek-içi (in-memory) mock'lar çalışır;
cevaplar gerçekçi ve deterministiktir. Gerçek bileşenler aynı arayüzlerin arkasına takılacaktır.

**Hata formatı:** Tüm 4xx/5xx cevapları (422 dahil) aynı şekildedir:
`{"error": {"code": "NOT_FOUND", "message": "...", "details": null}}`

**Sayfalama:** Liste uçları `?page=1&page_size=20` (en fazla 100) alır,
`{"items": [...], "total": 42, "page": 1, "page_size": 20}` döner.

**Kimlik doğrulama:** `Authorization: Bearer <access_token>` ("Authorize" butonu). `AUTH_ENABLED=false` iken
tüm istekler demo kullanıcıyla (ADMIN) çalışır. Demo hesap: `demo@aerospace.local` / `demo12345`.
Auth uçları şimdilik `/auth/*`, birleştirmede `/api/v1/auth/*` olacak.

**Uzun işler:** PDF/rapor yükleme `202 Accepted` döner; durum `GET .../index-status` veya `GET /reports/{id}`
ile yoklanır (`PENDING → INDEXED`, `UPLOADED → READY`).
"""

OPENAPI_TAGS: list[dict[str, str]] = [
    {"name": "System", "description": "Uygulama bilgisi, sağlık kontrolü ve enum değerleri. Auth istemez."},
    {"name": "Auth", "description": "Kayıt, giriş, token yenileme ve oturumdaki kullanıcı (Taha'nın modülü)."},
    {"name": "Standards", "description": "Standart kataloğu, standart PDF'i yükleme ve indeksleme durumu."},
    {"name": "Search & Chat", "description": "Standartlarda arama ve kaynak gösteren soru-cevap (RAG) sohbeti."},
    {"name": "Reports", "description": "Teknik rapor yükleme ve standarda göre uyumluluk analizi."},
]


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Uygulama açılırken bir kez, kapanırken bir kez çalışır.

    Ağır/paylaşılan nesneler (bellek-içi repository'ler + seed verisi, arama, LLM, dosya deposu) burada
    **bir kez** oluşturulup `app.state`'e konur (`src/core/deps.py` → `init_app_state`); istek başına yaratılmaz.
    """
    settings = get_settings()
    setup_logging(settings.LOG_LEVEL)
    logger.info(
        "{} v{} başlıyor (auth={}, search={}, llm={})",
        settings.APP_NAME, settings.APP_VERSION, settings.AUTH_ENABLED,
        settings.SEARCH_PROVIDER, settings.LLM_PROVIDER,
    )
    init_app_state(app, settings)
    yield
    logger.info("{} kapanıyor", settings.APP_NAME)


def _install_openapi_security(app: FastAPI) -> None:
    """Swagger'daki "Authorize" butonu için HTTPBearer şemasını OpenAPI'ye her zaman ekler.

    FastAPI bu şemayı ancak bir endpoint `get_current_user`'ı kullandığında otomatik ekler. Faz 1'de korumalı
    endpoint olmadığı için şemayı burada elle koyuyoruz. Ad ("HTTPBearer") FastAPI'nin otomatik adıyla aynı;
    Faz 3'te korumalı uçlar gelince aynı kayıt kullanılır, çift kayıt oluşmaz.
    """

    def custom_openapi() -> dict[str, Any]:
        if app.openapi_schema:
            return app.openapi_schema
        schema = get_openapi(
            title=app.title, version=app.version, description=app.description,
            routes=app.routes, tags=app.openapi_tags,
        )
        schemes = schema.setdefault("components", {}).setdefault("securitySchemes", {})
        schemes.setdefault("HTTPBearer", {
            "type": "http", "scheme": "bearer",
            "description": "Giriş (`/auth/login`) sonrası alınan access token.",
        })
        _use_error_response_for_422(schema)
        app.openapi_schema = schema
        return schema

    app.openapi = custom_openapi  # type: ignore[method-assign]


_ERROR_RESPONSE_REF = "#/components/schemas/ErrorResponse"
_FASTAPI_VALIDATION_SCHEMAS = ("HTTPValidationError", "ValidationError")


def _use_error_response_for_422(schema: dict[str, Any]) -> None:
    """Swagger'daki tüm 422 cevaplarını FastAPI'nin `HTTPValidationError`'ı yerine `ErrorResponse`'a yönlendirir.

    Neden: FastAPI parametre/gövde alan her endpoint'e kendi 422 şemasını otomatik ekler; ama bizim global
    handler'ımız (`src/core/errors.py`) 422'yi de `{"error": {...}}` formatında döner. Belge gerçeği
    göstersin diye burada **toplu** düzeltiyoruz; router'lara tek tek `422` yazmak gerekmez.
    Sadece belgeyi (OpenAPI) değiştirir, çalışma anındaki davranış aynıdır.
    """
    components = schema.setdefault("components", {}).setdefault("schemas", {})
    if "ErrorResponse" not in components:
        generated = ErrorResponse.model_json_schema(ref_template="#/components/schemas/{model}")
        components.update(generated.pop("$defs", {}))
        components["ErrorResponse"] = generated
    for path_item in schema.get("paths", {}).values():
        for operation in path_item.values():
            if isinstance(operation, dict) and "422" in operation.get("responses", {}):
                operation["responses"]["422"] = {
                    "description": "Doğrulama hatası (VALIDATION_ERROR): hatalı alanlar `details` listesinde.",
                    "content": {"application/json": {"schema": {"$ref": _ERROR_RESPONSE_REF}}},
                }
    # Artık hiçbir yerden referans verilmeyen FastAPI doğrulama şemalarını temizle.
    removed = {name: components.pop(name) for name in _FASTAPI_VALIDATION_SCHEMAS if name in components}
    remaining = json.dumps(schema)
    for name, definition in removed.items():
        if f'"#/components/schemas/{name}"' in remaining:  # hâlâ kullanan varsa geri koy
            components[name] = definition


def create_app() -> FastAPI:
    """Uygulamayı kurar ve döner."""
    settings = get_settings()
    app = FastAPI(
        title="Aerospace Compliance Platform — Mobil API",
        description=API_DESCRIPTION,
        version=settings.APP_VERSION,
        openapi_tags=OPENAPI_TAGS,
        lifespan=lifespan,
    )
    register_exception_handlers(app)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials="*" not in settings.CORS_ORIGINS,  # "*" ile credentials birlikte kullanılamaz
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(system.router)
    # Auth şimdilik /auth/* (Taha'nın şekli). TODO(Taha): birleştirmede api_v1_router'a taşınacak → /api/v1/auth/*
    app.include_router(auth.router)
    app.include_router(api_v1_router)
    _install_openapi_security(app)
    return app


app = create_app()
