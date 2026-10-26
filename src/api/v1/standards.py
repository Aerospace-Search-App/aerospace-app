"""Standart uçları (`/api/v1/standards`): katalog, PDF yükleme (202) ve indeksleme durumu.

Router sadece doğrular → servisi çağırır → şemayı döner. İş kuralları `standards_service.py`'de.
"""

from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, File, Query, UploadFile

from src.api.responses import errors
from src.application.schemas.common import Page, PageParams, to_page
from src.application.schemas.standard import IndexStatusOut, StandardCreate, StandardOut
from src.application.services.standards_service import StandardsService
from src.core.deps import get_current_user, get_standards_service, require_admin
from src.domain.enums import IndexStatus, StandardStatus, StandardType

router = APIRouter(prefix="/standards", tags=["Standards"], dependencies=[Depends(get_current_user)])

Service = Annotated[StandardsService, Depends(get_standards_service)]
_NOT_FOUND = {404: "Standart bulunamadı (NOT_FOUND)."}
_ADMIN = {403: "Bu işlem için ADMIN rolü gerekli (FORBIDDEN)."}


@router.get(
    "",
    response_model=Page[StandardOut],
    status_code=200,
    summary="Standartları listele",
    description="Standart kataloğunu sayfalı döner. `q` kodda/başlıkta arar (büyük-küçük harf duyarsız); "
                "`standard_type`, `status`, `index_status` ile filtrelenebilir. Geçersiz enum değeri 422 döner.",
    responses=errors(auth=True),
)
def list_standards(
    svc: Service,
    paging: Annotated[PageParams, Query()],
    q: Annotated[str | None, Query(max_length=100, description="Kod veya başlıkta arama.",
                                   examples=["810"])] = None,
    standard_type: Annotated[StandardType | None, Query(description="Kaynak türü filtresi.")] = None,
    status: Annotated[StandardStatus | None, Query(description="Yürürlük durumu filtresi.")] = None,
    index_status: Annotated[IndexStatus | None, Query(description="İndeksleme durumu filtresi.")] = None,
) -> Page[StandardOut]:
    items, total = svc.list_standards(q=q, standard_type=standard_type, status=status, index_status=index_status,
                                      offset=paging.offset, limit=paging.page_size)
    return to_page(StandardOut, items, total, paging)


@router.post(
    "",
    response_model=StandardOut,
    status_code=201,
    summary="Standart ekle (ADMIN)",
    description="Kataloğa yeni standart ekler. Kod benzersizdir (büyük/küçük harf duyarsız); aynı kod varsa 409. "
                "PDF'i ayrıca `POST /standards/{standard_id}/document` ile yüklenir.",
    responses=errors({**_ADMIN, 409: "Bu kodla standart zaten kayıtlı (CONFLICT)."}, auth=True),
    dependencies=[Depends(require_admin)],
)
def create_standard(body: StandardCreate, svc: Service) -> StandardOut:
    return StandardOut.model_validate(svc.create(body))


@router.get(
    "/{standard_id}",
    response_model=StandardOut,
    status_code=200,
    summary="Standart detayı",
    description="Tek bir standardın bilgilerini ve indeksleme özetini döner.",
    responses=errors(_NOT_FOUND, auth=True),
)
def get_standard(standard_id: int, svc: Service) -> StandardOut:
    return StandardOut.model_validate(svc.get(standard_id))


@router.post(
    "/{standard_id}/document",
    response_model=IndexStatusOut,
    status_code=202,
    summary="Standart PDF'ini yükle ve indeksle (ADMIN)",
    description="PDF'i kaydeder ve indekslemeyi arka planda başlatır; hemen 202 + `PENDING` döner. Mobil uygulama "
                "`GET .../index-status`'u ~2 sn'de bir yoklar, `INDEXED` veya `FAILED` olunca durur. "
                "Sadece `%PDF` imzalı `.pdf` dosyalar, en fazla `MAX_UPLOAD_MB`.",
    responses=errors({**_ADMIN, **_NOT_FOUND, 409: "İndeksleme zaten sürüyor (CONFLICT).",
                      413: "Dosya boyut sınırını aşıyor (PAYLOAD_TOO_LARGE).",
                      415: "Dosya PDF değil (UNSUPPORTED_FILE)."}, auth=True),
    dependencies=[Depends(require_admin)],
)
def upload_document(standard_id: int, background_tasks: BackgroundTasks, svc: Service,
                    file: UploadFile = File(..., description="Standardın PDF dosyası.")) -> IndexStatusOut:
    # TODO(Onur): standart PDF'leri bu uçla (ve web arayüzünden) yüklenecek; parçalama Sudenur'un SearchService'inde.
    state = svc.upload_document(standard_id, file.file, file.filename)
    background_tasks.add_task(svc.index_document, standard_id)
    return IndexStatusOut.model_validate(state)


@router.get(
    "/{standard_id}/index-status",
    response_model=IndexStatusOut,
    status_code=200,
    summary="İndeksleme durumu",
    description="PDF indekslemesinin durumunu (`PENDING → PROCESSING → INDEXED / FAILED`), ilerlemesini ve "
                "hata mesajını döner. Yükleme sonrası polling için kullanılır.",
    responses=errors(_NOT_FOUND, auth=True),
)
def get_index_status(standard_id: int, svc: Service) -> IndexStatusOut:
    return IndexStatusOut.model_validate(svc.get_index_status(standard_id))
