"""Sürümlü API (`/api/v1`). Alt router'lar buraya eklenir; `main.py` sadece bu tek router'ı bağlar.

Neden `/api/v1`? İleride uyumsuz bir değişiklik gerekirse `/api/v2` açılır, eski mobil sürümler bozulmaz.
"""

from fastapi import APIRouter

from src.api.v1 import chat, meta, reports, search, standards
from src.core.config import get_settings

api_v1_router = APIRouter(prefix=get_settings().API_V1_PREFIX)
api_v1_router.include_router(meta.router)
api_v1_router.include_router(standards.router)
api_v1_router.include_router(search.router)
api_v1_router.include_router(chat.router)
api_v1_router.include_router(reports.router)
