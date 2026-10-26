"""Ortak şemalar: tek tip hata cevabı ve sayfalı liste.

- `ErrorResponse`: TÜM 4xx/5xx cevaplarının şekli (422 dahil). Router'larda `responses={404: {"model": ErrorResponse}}`
  diye verilir ki Swagger'da hata cevabı da belgelensin. Gövdeyi üreten kod: `src/core/errors.py`.
- `Page[T]`: liste endpoint'lerinin cevabı (`?page=1&page_size=20` → `{items, total, page, page_size}`).
  Örn. `Page[StandardOut]` (Faz 3).
"""

from collections.abc import Sequence
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ErrorDetail(BaseModel):
    """Hatanın kendisi: makinenin okuyacağı `code`, kullanıcıya gösterilecek Türkçe `message`, opsiyonel `details`."""

    code: str = Field(..., description="Sabit hata kodu (büyük harf).", examples=["NOT_FOUND"])
    message: str = Field(..., description="Türkçe, kullanıcıya gösterilebilir mesaj.",
                         examples=["Standart bulunamadı: id=7"])
    details: Any | None = Field(
        default=None,
        description="Ek bilgi. 422'de hatalı alanların listesi, diğerlerinde genellikle null.",
        examples=[None, [{"field": "body.email", "message": "value is not a valid email address"}]],
    )


class ErrorResponse(BaseModel):
    """Tek tip hata zarfı: `{"error": {"code", "message", "details"}}`."""

    model_config = ConfigDict(json_schema_extra={"example": {
        "error": {"code": "NOT_FOUND", "message": "Standart bulunamadı: id=7", "details": None},
    }})

    error: ErrorDetail


class Page[T](BaseModel):
    """Sayfalı liste cevabı. `T` listelenen nesnenin şemasıdır (ör. `Page[StandardOut]`)."""

    model_config = ConfigDict(json_schema_extra={"example": {
        "items": [], "total": 42, "page": 1, "page_size": 20,
    }})

    items: list[T] = Field(..., description="Bu sayfadaki kayıtlar.")
    total: int = Field(..., ge=0, description="Filtreye uyan toplam kayıt sayısı.", examples=[42])
    page: int = Field(..., ge=1, description="Sayfa numarası (1'den başlar).", examples=[1])
    page_size: int = Field(..., ge=1, description="Sayfa başına kayıt sayısı (en fazla 100).", examples=[20])


# Sözleşme §0: `?page=1&page_size=20`, page_size en fazla 100 (meta/enums `limits.max_page_size` ile aynı).
DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100


class PageParams(BaseModel):
    """Liste uçlarının sayfalama sorgu parametreleri.

    Router'da FastAPI'nin "query parameter model" özelliğiyle kullanılır (bu dosya FastAPI'ye bağımlı kalmaz):

        def list_standards(paging: Annotated[PageParams, Query()]) -> Page[StandardOut]: ...

    Sınırların dışındaki değerler (page=0, page_size=101) otomatik 422 `VALIDATION_ERROR` olur.
    """

    model_config = ConfigDict(json_schema_extra={"examples": [{"page": 1, "page_size": 20}]})

    page: int = Field(default=1, ge=1, description="Sayfa numarası (1'den başlar).", examples=[1])
    page_size: int = Field(default=DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE,
                           description="Sayfa başına kayıt sayısı (1–100).", examples=[20])

    @property
    def offset(self) -> int:
        """Atlanacak kayıt sayısı (repository'ler dilimleme için kullanır)."""
        return (self.page - 1) * self.page_size


def to_page[T: BaseModel](schema: type[T], items: Sequence[object], total: int, paging: PageParams) -> Page[T]:
    """Servisten gelen entity listesini `Page[schema]` cevabına çevirir (her router aynı şekilde sayfalasın).

        return to_page(StandardOut, items, total, paging)
    """
    return Page[schema](  # type: ignore[valid-type]
        items=[schema.model_validate(item) for item in items], total=total,
        page=paging.page, page_size=paging.page_size,
    )
