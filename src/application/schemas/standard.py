"""Standart şemaları (sözleşme §4) — çekirdek set: liste, ekleme, detay, PDF yükleme, indeks durumu.

- `StandardCreate`: `POST /api/v1/standards` gövdesi (istek şeması).
- `StandardOut`: listede ve detayda dönen standart (cevap şeması).
- `IndexStatusOut`: PDF yükleme cevabı (202, `PENDING`) ve `GET .../index-status` cevabı.

PDF yükleme (`POST /standards/{id}/document`) `multipart/form-data` olduğu için istek şeması yoktur;
router'da `file: UploadFile = File(...)` ile alınır.
Sonraki iterasyonda: `StandardUpdate` (PATCH), `BulkUploadOut`, `RequirementOut`.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from src.domain.enums import IndexStatus, StandardStatus, StandardType

_STANDARD_EXAMPLE = {
    "id": 1,
    "code": "MIL-STD-810H",
    "title": "Environmental Engineering Considerations and Laboratory Tests",
    "standard_type": "MIL",
    "version": "H",
    "issuing_body": "U.S. Department of Defense",
    "publication_year": 2019,
    "description": "Askeri ekipmanların çevresel koşullara (titreşim, şok, sıcaklık, nem) dayanım test yöntemleri.",
    "status": "ACTIVE",
    "index_status": "INDEXED",
    "is_indexed": True,
    "has_document": True,
    "page_count": 1089,
    "chunk_count": 5210,
    "requirement_count": 312,
    "indexed_at": "2026-10-26T09:30:00Z",
    "created_at": "2026-10-26T09:00:00Z",
    "updated_at": "2026-10-26T09:30:00Z",
}


class StandardCreate(BaseModel):
    """`POST /api/v1/standards` gövdesi. `code` benzersizdir (büyük/küçük harf duyarsız; aynıysa 409)."""

    model_config = ConfigDict(str_strip_whitespace=True, json_schema_extra={"examples": [{
        "code": "MIL-STD-810H",
        "title": "Environmental Engineering Considerations and Laboratory Tests",
        "standard_type": "MIL",
        "version": "H",
        "issuing_body": "U.S. Department of Defense",
        "publication_year": 2019,
        "description": None,
    }]})

    code: str = Field(..., min_length=1, max_length=50, description="Standart kodu (benzersiz).",
                      examples=["MIL-STD-810H"])
    title: str = Field(..., min_length=1, max_length=300, description="Standardın tam adı.",
                       examples=["Environmental Engineering Considerations and Laboratory Tests"])
    standard_type: StandardType = Field(..., description="Kaynak türü: MIL, CIVIL, INTL.", examples=["MIL"])
    version: str | None = Field(default=None, max_length=20, description="Revizyon/sürüm harfi.",
                                examples=["H"])
    issuing_body: str | None = Field(default=None, max_length=200, description="Yayımlayan kurum.",
                                     examples=["U.S. Department of Defense"])
    publication_year: int | None = Field(default=None, ge=1900, le=2100, description="Yayın yılı (1900–2100).",
                                         examples=[2019])
    description: str | None = Field(default=None, max_length=2000, description="Kısa açıklama.",
                                    examples=[None])


class StandardOut(BaseModel):
    """Standart kartı. `is_indexed` aramaya hazır olup olmadığını, `has_document` PDF'in yüklü olup olmadığını söyler."""

    model_config = ConfigDict(from_attributes=True, json_schema_extra={"examples": [_STANDARD_EXAMPLE]})

    id: int = Field(..., description="Standart kimliği.", examples=[1])
    code: str = Field(..., description="Standart kodu.", examples=["MIL-STD-810H"])
    title: str = Field(..., description="Standardın tam adı.",
                       examples=["Environmental Engineering Considerations and Laboratory Tests"])
    standard_type: StandardType = Field(..., description="Kaynak türü.", examples=["MIL"])
    version: str | None = Field(default=None, description="Revizyon/sürüm.", examples=["H"])
    issuing_body: str | None = Field(default=None, description="Yayımlayan kurum.",
                                     examples=["U.S. Department of Defense"])
    publication_year: int | None = Field(default=None, description="Yayın yılı.", examples=[2019])
    description: str | None = Field(default=None, description="Kısa açıklama.",
                                    examples=[_STANDARD_EXAMPLE["description"]])
    status: StandardStatus = Field(..., description="Yürürlük durumu.", examples=["ACTIVE"])
    index_status: IndexStatus = Field(..., description="PDF indeksleme durumu.", examples=["INDEXED"])
    is_indexed: bool = Field(..., description="Aramaya hazır mı (index_status == INDEXED).", examples=[True])
    has_document: bool = Field(..., description="Standardın PDF'i yüklü mü.", examples=[True])
    page_count: int | None = Field(default=None, ge=0, description="PDF sayfa sayısı (yüklenmediyse null).",
                                   examples=[1089])
    chunk_count: int = Field(default=0, ge=0, description="Aramada kullanılan metin parçası sayısı.",
                             examples=[5210])
    requirement_count: int = Field(default=0, ge=0, description="Çıkarılan gereksinim (madde) sayısı.",
                                   examples=[312])
    indexed_at: datetime | None = Field(default=None, description="İndekslemenin bittiği zaman (UTC).",
                                        examples=["2026-10-26T09:30:00Z"])
    created_at: datetime = Field(..., description="Oluşturulma zamanı (UTC).", examples=["2026-10-26T09:00:00Z"])
    updated_at: datetime = Field(..., description="Son güncelleme zamanı (UTC).", examples=["2026-10-26T09:30:00Z"])


class IndexStatusOut(BaseModel):
    """İndeksleme durumu. Mobil, PDF yükledikten sonra bunu ~2 sn'de bir yoklar; INDEXED/FAILED olunca durur."""

    model_config = ConfigDict(from_attributes=True, json_schema_extra={"examples": [{
        "standard_id": 1, "index_status": "PROCESSING", "progress": 0.4, "page_count": 1089,
        "chunk_count": 0, "error_message": None, "started_at": "2026-10-26T09:28:00Z", "finished_at": None,
    }]})

    standard_id: int = Field(..., description="Standart kimliği.", examples=[1])
    index_status: IndexStatus = Field(..., description="İndeksleme durumu.", examples=["PROCESSING"])
    progress: float = Field(..., ge=0, le=1, description="İlerleme oranı (0–1).", examples=[0.4])
    page_count: int | None = Field(default=None, ge=0, description="PDF sayfa sayısı.", examples=[1089])
    chunk_count: int = Field(default=0, ge=0, description="Şu ana kadar üretilen parça sayısı.", examples=[0])
    error_message: str | None = Field(default=None, description="FAILED ise Türkçe hata açıklaması.",
                                      examples=[None])
    started_at: datetime | None = Field(default=None, description="İndekslemenin başladığı zaman (UTC).",
                                        examples=["2026-10-26T09:28:00Z"])
    finished_at: datetime | None = Field(default=None, description="İndekslemenin bittiği zaman (UTC).",
                                         examples=[None])
