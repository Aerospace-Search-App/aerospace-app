"""Sistem endpoint'lerinin cevap şemaları (sözleşme §2): `GET /` ve `GET /health`."""

from typing import Literal

from pydantic import BaseModel, Field


class RootOut(BaseModel):
    """`GET /` cevabı: uygulamanın kimlik kartı ve nereden devam edileceği."""

    app: str = Field(..., examples=["Aerospace Compliance Platform"])
    version: str = Field(..., examples=["1.1.0"])
    docs: str = Field(..., description="Swagger arayüzünün yolu.", examples=["/docs"])
    api: str = Field(..., description="Sürümlü API'nin taban yolu.", examples=["/api/v1"])


class HealthChecks(BaseModel):
    """Bileşen bazında durum. Arama/LLM için aktif sağlayıcının adı ("mock", "gemini") ya da "error"."""

    database: str = Field(..., examples=["ok"])
    search: str = Field(..., examples=["mock"])
    llm: str = Field(..., examples=["mock"])


class HealthOut(BaseModel):
    """`GET /health` cevabı. Bir bileşen çalışmıyorsa `status="degraded"` olur ama HTTP kodu yine 200'dür."""

    status: Literal["ok", "degraded"] = Field(..., examples=["ok"])
    version: str = Field(..., examples=["1.1.0"])
    checks: HealthChecks
