"""Rapor uçları (`/api/v1/reports`): rapor yükleme (202), listeleme, detay ve uyumluluk analizi (201).

Raporlar kullanıcıya özeldir: sadece kendi raporlarınızı görürsünüz, başkasınınki 404 döner.
"""

from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, Query, UploadFile

from src.api.responses import errors
from src.application.schemas.common import Page, PageParams, to_page
from src.application.schemas.report import AnalysisCreate, AnalysisOut, ReportOut
from src.application.services.analysis_service import AnalysisService
from src.application.services.report_service import ReportService
from src.core.deps import get_analysis_service, get_current_user, get_report_service
from src.domain.entities import User
from src.domain.enums import ReportStatus, ReportType

router = APIRouter(prefix="/reports", tags=["Reports"])

Service = Annotated[ReportService, Depends(get_report_service)]
CurrentUser = Annotated[User, Depends(get_current_user)]
_NOT_FOUND = {404: "Rapor bulunamadı veya size ait değil (NOT_FOUND)."}


@router.post(
    "",
    response_model=ReportOut,
    status_code=202,
    summary="Rapor yükle",
    description="Teknik rapor PDF'ini yükler; işleme arka planda yapılır ve hemen 202 + `UPLOADED` döner. Mobil "
                "uygulama `GET /reports/{report_id}`'yi ~2 sn'de bir yoklar; `READY` olunca analiz yapılabilir. "
                "`title` verilmezse dosya adından türetilir.",
    responses=errors({413: "Dosya boyut sınırını aşıyor (PAYLOAD_TOO_LARGE).",
                      415: "Dosya PDF değil (UNSUPPORTED_FILE)."}, auth=True),
)
def upload_report(
    user: CurrentUser, svc: Service, background_tasks: BackgroundTasks,
    file: UploadFile = File(..., description="Rapor PDF'i."),
    title: str | None = Form(None, max_length=200, description="Rapor başlığı (opsiyonel)."),
    report_type: ReportType = Form(ReportType.DESIGN, description="Rapor türü."),
) -> ReportOut:
    report = svc.upload(user, file.file, file.filename, title, report_type)
    background_tasks.add_task(svc.process, report.id)
    return ReportOut.model_validate(report)


@router.get(
    "",
    response_model=Page[ReportOut],
    status_code=200,
    summary="Raporlarım",
    description="Kullanıcının raporlarını en yeniden eskiye, sayfalı döner. `status`, `report_type` ve `q` "
                "(başlık/dosya adı) ile filtrelenebilir.",
    responses=errors(auth=True),
)
def list_reports(
    user: CurrentUser, svc: Service, paging: Annotated[PageParams, Query()],
    status: Annotated[ReportStatus | None, Query(description="İşleme durumu filtresi.")] = None,
    report_type: Annotated[ReportType | None, Query(description="Rapor türü filtresi.")] = None,
    q: Annotated[str | None, Query(max_length=100, description="Başlıkta/dosya adında arama.",
                                   examples=["titreşim"])] = None,
) -> Page[ReportOut]:
    items, total = svc.list_reports(user, status=status, report_type=report_type, q=q,
                                    offset=paging.offset, limit=paging.page_size)
    return to_page(ReportOut, items, total, paging)


@router.get(
    "/{report_id}",
    response_model=ReportOut,
    status_code=200,
    summary="Rapor detayı",
    description="Raporun bilgilerini ve işleme durumunu döner (yükleme sonrası polling için).",
    responses=errors(_NOT_FOUND, auth=True),
)
def get_report(report_id: int, user: CurrentUser, svc: Service) -> ReportOut:
    return ReportOut.model_validate(svc.get(user, report_id))


@router.post(
    "/{report_id}/analyses",
    response_model=AnalysisOut,
    status_code=201,
    summary="Uyumluluk analizi yap",
    description="Raporu seçili standartların ilgili maddeleriyle karşılaştırır ve kararı (`verdict`), güveni ve "
                "kaynaklı gerekçeyi döner. Rapor `READY` olmalı. Mock modda karar `INSUFFICIENT`, güven 0.5'tir.",
    responses=errors({**_NOT_FOUND, 409: "Rapor henüz analize hazır değil (CONFLICT).",
                      503: "Dil modeli kullanılamıyor; analiz kaydedilmedi (LLM_UNAVAILABLE)."}, auth=True),
)
def create_analysis(report_id: int, body: AnalysisCreate, user: CurrentUser,
                    svc: Annotated[AnalysisService, Depends(get_analysis_service)]) -> AnalysisOut:
    analysis = svc.create(user, report_id, body.query, body.standard_ids, body.top_k)
    return AnalysisOut.model_validate(analysis)
