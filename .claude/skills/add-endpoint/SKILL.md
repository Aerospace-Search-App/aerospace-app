---
name: add-endpoint
description: Projeye yeni bir FastAPI endpoint'i eklerken veya mevcut birini sözleşmeye uydururken izlenecek adımlar (şema → servis → router → kayıt → test). Endpoint ekleme/değiştirme işlerinde kullan.
---

# Endpoint ekleme reçetesi

Önce `docs/API_CONTRACT.md`'de endpoint'in satırını ve şemalarını bul. Yoksa dur → `api-contract-sync`.
Canlı örnek: `src/api/v1/standards.py` (router) ve `src/application/services/standards_service.py` (servis).

## 1. Şema — `src/application/schemas/<alan>.py`
```python
from pydantic import BaseModel, ConfigDict, Field

from src.domain.enums import StandardType

class StandardOut(BaseModel):
    """Listede ve detayda dönen standart (cevap şeması)."""

    model_config = ConfigDict(from_attributes=True, json_schema_extra={"examples": [{
        "id": 1, "code": "MIL-STD-810H", "title": "Environmental Engineering ...", "standard_type": "MIL",
    }]})
    id: int
    code: str = Field(..., examples=["MIL-STD-810H"])
    standard_type: StandardType
    ...
```
- Girdi şemaları: `XxxCreate`, `XxxUpdate` (tüm alanlar `| None = None`), çıktı: `XxxOut`. Liste: `Page[XxxOut]`
  (`src/application/schemas/common.py`: `Page`, `PageParams`, `to_page`).
- Kısıtlar şemada: `Field(min_length=3, max_length=2000)`, `Field(ge=1, le=20)`.
- Enum'lar `src/domain/enums.py`'deki enum'lardır; şemada tekrar tanımlanmaz.

## 2. Servis — `src/application/services/<alan>_service.py`
```python
from src.core.errors import NotFoundError
from src.domain.entities import Standard
from src.domain.interfaces import FileStorage, SearchService, StandardRepository

class StandardsService:
    """Standart kataloğu ve indeksleme iş kuralları."""

    def __init__(self, standards: StandardRepository, search: SearchService, storage: FileStorage) -> None:
        self._standards = standards
        self._search = search
        self._storage = storage

    def get(self, standard_id: int) -> Standard:
        standard = self._standards.get(standard_id)
        if standard is None:
            raise NotFoundError(f"Standart bulunamadı: id={standard_id}")
        return standard
```
- Somut sınıfa değil arayüze (`src/domain/interfaces.py` → `StandardRepository`, `SearchService`, `FileStorage`, `LLMClient`) bağımlıdır.
- HTTP bilmez (HTTPException, Request yok). `AppError` alt sınıfları (`src/core/errors.py`) fırlatır.
- Sahiplik kontrolü servis içinde: başkasının kaydı → `NotFoundError`.

## 3. Dependency — `src/core/deps.py`
```python
def get_standards_service(request: Request) -> StandardsService:
    s = request.app.state            # init_app_state (lifespan) içinde bir kez oluşturulan repo / mock'lar
    return StandardsService(s.standard_repo, s.search, s.storage)
```
Yeni paylaşılan nesne gerekiyorsa `init_app_state` içinde oluşturup `app.state`'e koy; istek başına yaratma.
Gerçek implementasyon (PostgreSQL, hibrit arama, Gemini) gelince sadece `init_app_state`'teki satır değişir.

## 4. Router — `src/api/v1/<alan>.py`
```python
from typing import Annotated

from fastapi import APIRouter, Depends

from src.api.responses import errors
from src.application.schemas.standard import StandardOut
from src.application.services.standards_service import StandardsService
from src.core.deps import get_current_user, get_standards_service

router = APIRouter(prefix="/standards", tags=["Standards"], dependencies=[Depends(get_current_user)])

Service = Annotated[StandardsService, Depends(get_standards_service)]
_NOT_FOUND = {404: "Standart bulunamadı (NOT_FOUND)."}


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
```
- Kimlik kontrolü router seviyesinde (`dependencies=[Depends(get_current_user)]`); fonksiyona `user` parametresi
  sadece kullanıcı bilgisi gerçekten lazımsa eklenir.
- `responses=errors({kod: "açıklama"}, auth=True)` (`src/api/responses.py`) her kodu `ErrorResponse`'a bağlar,
  `auth=True` 401'i ekler. 422'yi ekleme (otomatik).
- try/except yazma (global handler var). 🔒A endpoint'lerde decorator'a `dependencies=[Depends(require_admin)]`.
- 202 dönenler: `background_tasks: BackgroundTasks` parametresi; işi yapan metot serviste
  (`background_tasks.add_task(svc.index_document, standard_id)`).
- Dosya dönenler: `FileResponse(path, media_type="application/pdf", filename=original_name)`,
  `response_class=FileResponse`, `responses={200: {"content": {"application/pdf": {}}}}`.
- Statik yollar (`/bulk-upload`) parametreli yollardan (`/{standard_id}`) **önce** tanımlanır.

## 5. Kayıt — `src/api/v1/__init__.py`
`api_v1_router.include_router(<alan>.router)` — yoksa ekle.

## 6. Test — `tests/api/test_<alan>.py`
Mutlu yol + en az bir hata yolu. `test_contract_coverage.py`'deki beklenen listede satır var mı kontrol et.

## 7. Doğrula
```bash
.venv/Scripts/python -c "from main import app; print(len(app.openapi()['paths']))"
.venv/Scripts/python -m pytest tests/api -q
```

Ayrıntı: `docs/BACKEND_GELISTIRME_REHBERI.md` §6
