"""`GET /api/v1/meta/enums` cevap şeması (sözleşme §2).

Mobil uygulama dropdown'larını ve etiketlerini buradan doldurur; enum değerlerini koduna gömmez.
Böylece yeni bir değer eklendiğinde mobil uygulamayı yeniden yayınlamak gerekmez.
"""

from pydantic import BaseModel, Field

from src.domain.enums import (
    ComplianceVerdict,
    IndexStatus,
    ReportStatus,
    ReportType,
    RequirementCategory,
    SearchMode,
    StandardStatus,
    StandardType,
)


class VerdictOption(BaseModel):
    """Uyumluluk kararı ve ekranda gösterilecek Türkçe/İngilizce etiketi."""

    value: ComplianceVerdict = Field(..., examples=["COMPLIANT"])
    label_tr: str = Field(..., examples=["Uyumlu"])
    label_en: str = Field(..., examples=["Compliant"])


class Limits(BaseModel):
    """İstemcinin bilmesi gereken sınırlar (yükleme sınırı ayardan, top_k/page_size şema sabitlerinden gelir)."""

    max_upload_mb: int = Field(..., description="En büyük PDF boyutu (MB).", examples=[50])
    max_top_k: int = Field(..., description="Aramada istenebilecek en fazla sonuç.", examples=[20])
    max_page_size: int = Field(..., description="Liste endpoint'lerinde en büyük sayfa boyutu.", examples=[100])


class EnumsOut(BaseModel):
    """Tüm enum değerleri + sınırlar."""

    standard_types: list[StandardType] = Field(..., examples=[["MIL", "CIVIL", "INTL"]])
    standard_statuses: list[StandardStatus] = Field(..., examples=[["ACTIVE", "SUPERSEDED", "ARCHIVED"]])
    index_statuses: list[IndexStatus] = Field(
        ..., examples=[["NOT_INDEXED", "PENDING", "PROCESSING", "INDEXED", "FAILED"]])
    requirement_categories: list[RequirementCategory] = Field(
        ..., examples=[["ENVIRONMENTAL", "EMC", "SOFTWARE", "STRUCTURAL", "SAFETY"]])
    report_types: list[ReportType] = Field(..., examples=[["DESIGN", "TEST", "QUAL", "COMPLIANCE"]])
    report_statuses: list[ReportStatus] = Field(..., examples=[["UPLOADED", "PROCESSING", "READY", "FAILED"]])
    verdicts: list[VerdictOption] = Field(..., examples=[[
        {"value": "COMPLIANT", "label_tr": "Uyumlu", "label_en": "Compliant"},
        {"value": "PARTIAL", "label_tr": "Kısmen Uyumlu", "label_en": "Partially Compliant"},
        {"value": "NON_COMPLIANT", "label_tr": "Uyumsuz", "label_en": "Non-Compliant"},
        {"value": "INSUFFICIENT", "label_tr": "Yetersiz Bilgi", "label_en": "Insufficient Information"},
    ]])
    search_modes: list[SearchMode] = Field(..., examples=[["semantic", "keyword", "hybrid"]])
    limits: Limits
