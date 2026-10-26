"""Swagger'daki hata cevaplarını kısa yazmak için yardımcı.

    responses=errors({404: "Standart bulunamadı"}, auth=True)

her kodu `ErrorResponse` şemasına bağlar. `auth=True` ise 401 de eklenir (korumalı uçlar). 422 eklemeye gerek yok:
FastAPI otomatik ekler, `main.py` onu da `ErrorResponse`'a yönlendirir.
"""

from typing import Any

from src.application.schemas.common import ErrorResponse

UNAUTHORIZED_DESCRIPTION = "Token eksik veya geçersiz (UNAUTHORIZED). `AUTH_ENABLED=false` iken oluşmaz."


def errors(descriptions: dict[int, str] | None = None, *, auth: bool = False) -> dict[int | str, dict[str, Any]]:
    """`{kod: açıklama}` sözlüğünü FastAPI `responses=` biçimine çevirir."""
    items = dict(descriptions or {})
    if auth:
        items = {401: UNAUTHORIZED_DESCRIPTION, **items}
    return {code: {"model": ErrorResponse, "description": text} for code, text in sorted(items.items())}
