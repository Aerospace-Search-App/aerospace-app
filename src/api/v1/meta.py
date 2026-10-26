"""`GET /api/v1/meta/enums`: mobil uygulamanın dropdown ve etiketleri için tüm enum'lar + sınırlar."""

from fastapi import APIRouter, Depends

from src.application.schemas import common, search
from src.application.schemas.common import ErrorResponse
from src.application.schemas.meta import EnumsOut, Limits, VerdictOption
from src.core.config import Settings, get_settings
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

router = APIRouter(prefix="/meta", tags=["System"])


@router.get(
    "/enums",
    response_model=EnumsOut,
    status_code=200,
    summary="Enum değerleri ve sınırlar",
    description="Mobil uygulamanın seçim listeleri için tüm enum değerlerini, karar etiketlerini ve "
                "yükleme/arama/sayfalama sınırlarını döner.",
    responses={500: {"model": ErrorResponse, "description": "Beklenmeyen hata"}},
)
def get_enums(settings: Settings = Depends(get_settings)) -> EnumsOut:
    return EnumsOut(
        standard_types=list(StandardType),
        standard_statuses=list(StandardStatus),
        index_statuses=list(IndexStatus),
        requirement_categories=list(RequirementCategory),
        report_types=list(ReportType),
        report_statuses=list(ReportStatus),
        verdicts=[VerdictOption(value=v, label_tr=v.label_tr, label_en=v.label_en) for v in ComplianceVerdict],
        search_modes=list(SearchMode),
        # Tek kaynak: top_k/page_size sınırları şemalardaki sabitlerden (doğrulama da onları kullanır),
        # yükleme sınırı ayardan (dosya deposu da onu kullanır).
        limits=Limits(max_upload_mb=settings.MAX_UPLOAD_MB, max_top_k=search.MAX_TOP_K,
                      max_page_size=common.MAX_PAGE_SIZE),
    )
