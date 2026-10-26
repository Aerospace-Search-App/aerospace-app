"""Rapor ve uyumluluk analizi şemaları (sözleşme §6) — çekirdek set: yükleme, liste, detay, analiz.

Rapor yükleme (`POST /api/v1/reports`) `multipart/form-data` olduğu için **istek şeması yoktur**: router'da
`file: UploadFile = File(...)`, `title: str | None = Form(None)`, `report_type: ReportType = Form(ReportType.DESIGN)`
ile alınır. Cevabı `ReportOut`'tur (202, `UPLOADED` / `PROCESSING`).
Sonraki iterasyonda: `ComplianceSummaryOut` (`GET /reports/{id}/summary`).
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, computed_field

from src.application.schemas.search import DEFAULT_TOP_K, MAX_TOP_K, SOURCE_EXAMPLE, SourceOut
from src.domain.enums import ComplianceVerdict, ReportStatus, ReportType

# Bu değer ve üstündeki güven skorları "yüksek güven" sayılır (AnalysisOut.is_high_confidence).
HIGH_CONFIDENCE_THRESHOLD = 0.8

_QUERY = "Rapor vibrasyon gereksinimlerini karşılıyor mu?"


class ReportOut(BaseModel):
    """Kullanıcının yüklediği teknik rapor. `status = READY` olunca analiz yapılabilir."""

    model_config = ConfigDict(from_attributes=True, json_schema_extra={"examples": [{
        "id": 3, "title": "Telsiz Titreşim Test Raporu", "original_filename": "rapor.pdf",
        "report_type": "TEST", "status": "READY", "file_size_kb": 812.4, "page_count": 24,
        "analysis_count": 2, "error_message": None,
        "uploaded_at": "2026-10-26T10:00:00Z", "processed_at": "2026-10-26T10:00:05Z",
    }]})

    id: int = Field(..., description="Rapor kimliği.", examples=[3])
    title: str = Field(..., description="Rapor başlığı (verilmezse dosya adından türetilir).",
                       examples=["Telsiz Titreşim Test Raporu"])
    original_filename: str = Field(..., description="Yüklenen dosyanın orijinal adı (sadece gösterim için).",
                                   examples=["rapor.pdf"])
    report_type: ReportType = Field(..., description="Rapor türü.", examples=["TEST"])
    status: ReportStatus = Field(..., description="İşleme durumu (UPLOADED → PROCESSING → READY / FAILED).",
                                 examples=["READY"])
    file_size_kb: float = Field(..., ge=0, description="Dosya boyutu (KB).", examples=[812.4])
    page_count: int | None = Field(default=None, ge=0, description="Sayfa sayısı (işlenmeden önce null).",
                                   examples=[24])
    analysis_count: int = Field(default=0, ge=0, description="Bu rapor için yapılmış analiz sayısı.",
                                examples=[2])
    error_message: str | None = Field(default=None, description="FAILED ise Türkçe hata açıklaması.",
                                      examples=[None])
    uploaded_at: datetime = Field(..., description="Yükleme zamanı (UTC).", examples=["2026-10-26T10:00:00Z"])
    processed_at: datetime | None = Field(default=None, description="İşlemenin bittiği zaman (UTC).",
                                          examples=["2026-10-26T10:00:05Z"])


class AnalysisCreate(BaseModel):
    """`POST /api/v1/reports/{report_id}/analyses` gövdesi: rapor, seçilen standartlara göre değerlendirilir."""

    model_config = ConfigDict(str_strip_whitespace=True, json_schema_extra={"examples": [
        {"query": _QUERY, "standard_ids": [1], "top_k": 5},
    ]})

    query: str = Field(..., min_length=3, max_length=2000, description="Analiz sorusu (3–2000 karakter).",
                       examples=[_QUERY])
    standard_ids: list[int] = Field(default_factory=list,
                                    description="Karşılaştırılacak standartlar. Boş liste = tümü.", examples=[[1]])
    top_k: int = Field(default=DEFAULT_TOP_K, ge=1, le=MAX_TOP_K,
                       description="Kullanılacak standart parçası sayısı (1–20).", examples=[5])


class AnalysisOut(BaseModel):
    """Uyumluluk analizi sonucu.

    `verdict_label` ve `is_high_confidence` saklanmaz, **hesaplanır** (`computed_field`):
    - `verdict_label` = kararın Türkçe etiketi (`ComplianceVerdict.label_tr`, ör. PARTIAL → "Kısmen Uyumlu"),
    - `is_high_confidence` = `confidence >= HIGH_CONFIDENCE_THRESHOLD` (0.8).
    Böylece etiket ve eşik tek yerde tanımlı kalır, veriyle çelişemez.
    """

    model_config = ConfigDict(from_attributes=True, json_schema_extra={"examples": [{
        "id": 12, "report_id": 3, "query": _QUERY, "verdict": "PARTIAL", "verdict_label": "Kısmen Uyumlu",
        "confidence": 0.78, "is_high_confidence": False,
        "reasoning": "[DEMO] Raporda titreşim profili ve süreleri verilmiş, ancak MIL-STD-810H Method 514.8'in "
                     "istediği üç eksenli test sonuçlarından yalnızca ikisi raporlanmış (Sayfa 412).",
        "sources": [SOURCE_EXAMPLE], "model": "gemini-2.5-flash", "duration_ms": 2400,
        "created_at": "2026-10-26T10:05:00Z",
    }]})

    id: int = Field(..., description="Analiz kimliği.", examples=[12])
    report_id: int = Field(..., description="Analiz edilen rapor.", examples=[3])
    query: str = Field(..., description="Analiz sorusu.", examples=[_QUERY])
    verdict: ComplianceVerdict = Field(..., description="Uyumluluk kararı.", examples=["PARTIAL"])
    confidence: float = Field(..., ge=0, le=1, description="Modelin karara güveni (0–1).", examples=[0.78])
    reasoning: str = Field(..., description="Kararın gerekçesi (kaynaklara atıfla).",
                           examples=["[DEMO] Raporda titreşim profili verilmiş, ancak üç eksenden yalnızca ikisi "
                                     "raporlanmış (Sayfa 412)."])
    sources: list[SourceOut] = Field(default_factory=list, description="Kararın dayandığı standart parçaları.",
                                     examples=[[SOURCE_EXAMPLE]])
    model: str = Field(..., description="Analizi yapan model adı.", examples=["gemini-2.5-flash"])
    duration_ms: int = Field(..., ge=0, description="Analiz süresi (milisaniye).", examples=[2400])
    created_at: datetime = Field(..., description="Analiz zamanı (UTC).", examples=["2026-10-26T10:05:00Z"])

    @computed_field(description="Kararın Türkçe etiketi (verdict'ten türetilir).",  # type: ignore[prop-decorator]
                    examples=["Kısmen Uyumlu"])
    @property
    def verdict_label(self) -> str:
        return self.verdict.label_tr

    @computed_field(description="Güven skoru 0.8 ve üstündeyse true.",  # type: ignore[prop-decorator]
                    examples=[False])
    @property
    def is_high_confidence(self) -> bool:
        return self.confidence >= HIGH_CONFIDENCE_THRESHOLD
