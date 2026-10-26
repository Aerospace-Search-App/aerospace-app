"""Domain enum'ları (sözleşme §0 "Enum'lar" tablosu, birebir).

Ne işe yarar: Bir alanın alabileceği sabit değerleri tek yerde tanımlar. `StrEnum` olduğu için JSON'da
düz metin olarak görünür ("MIL", "INDEXED" ...). Şemalarda ve sorgu parametrelerinde bu tipler kullanılır;
geçersiz bir değer gelirse FastAPI otomatik 422 döner.

Bu dosya sadece Python standart kütüphanesini kullanır (domain katmanı dış kütüphane import etmez).
Mobil uygulama bu değerleri koda gömmez, `GET /api/v1/meta/enums`'tan okur.
"""

from enum import StrEnum


class StandardType(StrEnum):
    """Standardın kaynağı: askeri, sivil havacılık, uluslararası."""

    MIL = "MIL"
    CIVIL = "CIVIL"
    INTL = "INTL"


class StandardStatus(StrEnum):
    """Standardın yürürlük durumu."""

    ACTIVE = "ACTIVE"
    SUPERSEDED = "SUPERSEDED"
    ARCHIVED = "ARCHIVED"


class IndexStatus(StrEnum):
    """Standart PDF'inin arama için indekslenme durumu (PENDING → PROCESSING → INDEXED / FAILED)."""

    NOT_INDEXED = "NOT_INDEXED"
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    INDEXED = "INDEXED"
    FAILED = "FAILED"


class RequirementCategory(StrEnum):
    """Gereksinim (madde) kategorisi."""

    ENVIRONMENTAL = "ENVIRONMENTAL"
    EMC = "EMC"
    SOFTWARE = "SOFTWARE"
    STRUCTURAL = "STRUCTURAL"
    SAFETY = "SAFETY"


class ReportType(StrEnum):
    """Yüklenen teknik raporun türü."""

    DESIGN = "DESIGN"
    TEST = "TEST"
    QUAL = "QUAL"
    COMPLIANCE = "COMPLIANCE"


class ReportStatus(StrEnum):
    """Rapor işleme durumu (UPLOADED → PROCESSING → READY / FAILED). READY = analize hazır."""

    UPLOADED = "UPLOADED"
    PROCESSING = "PROCESSING"
    READY = "READY"
    FAILED = "FAILED"


class ComplianceVerdict(StrEnum):
    """Uyumluluk analizi kararı. `label_tr` / `label_en` ekranda gösterilecek etiketi verir."""

    COMPLIANT = "COMPLIANT"
    PARTIAL = "PARTIAL"
    NON_COMPLIANT = "NON_COMPLIANT"
    INSUFFICIENT = "INSUFFICIENT"

    @property
    def label_tr(self) -> str:
        """Türkçe etiket (ör. "Kısmen Uyumlu")."""
        return _VERDICT_LABELS[self][0]

    @property
    def label_en(self) -> str:
        """İngilizce etiket (ör. "Partially Compliant")."""
        return _VERDICT_LABELS[self][1]


_VERDICT_LABELS: dict[ComplianceVerdict, tuple[str, str]] = {
    ComplianceVerdict.COMPLIANT: ("Uyumlu", "Compliant"),
    ComplianceVerdict.PARTIAL: ("Kısmen Uyumlu", "Partially Compliant"),
    ComplianceVerdict.NON_COMPLIANT: ("Uyumsuz", "Non-Compliant"),
    ComplianceVerdict.INSUFFICIENT: ("Yetersiz Bilgi", "Insufficient Information"),
}


class SearchMode(StrEnum):
    """Arama modu (küçük harf, sözleşmedeki gibi): anlamsal, anahtar kelime veya ikisinin karışımı."""

    SEMANTIC = "semantic"
    KEYWORD = "keyword"
    HYBRID = "hybrid"


class ChatStatus(StrEnum):
    """Sohbet cevabının durumu."""

    ANSWERED = "ANSWERED"
    NO_RESULTS = "NO_RESULTS"
    LLM_UNAVAILABLE = "LLM_UNAVAILABLE"


class UserRole(StrEnum):
    """Kullanıcı rolü. ENGINEER varsayılan, ADMIN standart ekleyip PDF yükleyebilir."""

    ENGINEER = "ENGINEER"
    ADMIN = "ADMIN"
