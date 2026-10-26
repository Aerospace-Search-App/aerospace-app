"""Domain entity'leri: iş dünyasındaki nesnelerin saf Python hali (veritabanı / HTTP bilmez).

Ne işe yarar: Servisler bu nesnelerle çalışır; repository'ler bunları saklar, router'lar Pydantic şemalarına
(`StandardOut.model_validate(standard)`) çevirir. Bu dosya sadece Python standart kütüphanesini kullanır.

Benzetme: Bir uçağın "teknik çizimi" gibi; hangi fabrikada (bellek, PostgreSQL) üretildiğinden bağımsızdır.
TODO(Doruk): PostgreSQL modelleri (ORM) bu entity'lere eşlenecek; entity'ler değişmeden kalır.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone

from src.domain.enums import (
    ChatStatus,
    ComplianceVerdict,
    IndexStatus,
    ReportStatus,
    ReportType,
    StandardStatus,
    StandardType,
    UserRole,
)


def utc_now() -> datetime:
    """Şu anki zaman, her zaman UTC ve timezone'lu (eski koddaki `utcnow()` hatası tekrarlanmasın)."""
    return datetime.now(timezone.utc)


# --------------------------------------------------------------------------------------------- kullanıcı


@dataclass(frozen=True, slots=True)
class User:
    """İsteği yapan kullanıcı. `get_current_user` bunu döner.

    `password_hash` sadece auth servisinde kullanılır; hiçbir cevap şemasında yoktur ve `repr`'de görünmez.
    """

    id: int
    email: str
    full_name: str
    role: UserRole = UserRole.ENGINEER
    created_at: datetime = field(default_factory=utc_now)
    password_hash: str | None = field(default=None, repr=False)


# --------------------------------------------------------------------------------------------- standart


@dataclass(frozen=True, slots=True)
class IndexState:
    """Bir standardın indeksleme durumunun anlık görüntüsü (`GET .../index-status` cevabının kaynağı)."""

    standard_id: int
    index_status: IndexStatus
    progress: float
    page_count: int | None
    chunk_count: int
    error_message: str | None
    started_at: datetime | None
    finished_at: datetime | None


@dataclass(slots=True)
class Standard:
    """Katalogdaki bir standart (MIL-STD-810H vb.) ve PDF'inin indeksleme durumu."""

    code: str
    title: str
    standard_type: StandardType
    version: str | None = None
    issuing_body: str | None = None
    publication_year: int | None = None
    description: str | None = None
    status: StandardStatus = StandardStatus.ACTIVE
    index_status: IndexStatus = IndexStatus.NOT_INDEXED
    has_document: bool = False
    page_count: int | None = None
    chunk_count: int = 0
    requirement_count: int = 0
    indexed_at: datetime | None = None
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)
    # İndeksleme işinin ayrıntıları (cevapta IndexStatusOut olarak görünür).
    document_path: str | None = field(default=None, repr=False)
    index_progress: float = 0.0
    index_error: str | None = None
    index_started_at: datetime | None = None
    index_finished_at: datetime | None = None
    id: int = 0  # repository `add` sırasında atar

    @property
    def is_indexed(self) -> bool:
        """Aramaya hazır mı? (`index_status == INDEXED`)."""
        return self.index_status == IndexStatus.INDEXED

    def index_state(self) -> IndexState:
        """İndeksleme durumunu ayrı bir nesne olarak verir."""
        return IndexState(
            standard_id=self.id,
            index_status=self.index_status,
            progress=self.index_progress,
            page_count=self.page_count,
            chunk_count=self.chunk_count,
            error_message=self.index_error,
            started_at=self.index_started_at,
            finished_at=self.index_finished_at,
        )


@dataclass(frozen=True, slots=True)
class IndexResult:
    """`SearchService.index_document` sonucu: PDF'ten kaç sayfa / parça / gereksinim çıktı."""

    page_count: int
    chunk_count: int
    requirement_count: int


# --------------------------------------------------------------------------------------------- arama


@dataclass(frozen=True, slots=True)
class Source:
    """Aramanın bulduğu bir metin parçası (kaynak). Arama, sohbet ve analiz cevaplarında ortaktır."""

    chunk_id: str
    standard_id: int
    standard_code: str
    snippet: str
    score: float
    requirement_id: int | None = None
    section: str | None = None
    page: int | None = None


# --------------------------------------------------------------------------------------------- sohbet


@dataclass(slots=True)
class Message:
    """Sohbetteki bir soru-cevap çifti."""

    conversation_id: int
    question: str
    answer: str | None
    status: ChatStatus
    sources: list[Source] = field(default_factory=list)
    model: str = ""
    duration_ms: int = 0
    created_at: datetime = field(default_factory=utc_now)
    id: int = 0


@dataclass(slots=True)
class Conversation:
    """Bir kullanıcının sohbeti. `title` = ilk sorunun ilk 60 karakteri."""

    user_id: int
    title: str
    standard_ids: list[int] = field(default_factory=list)
    messages: list[Message] = field(default_factory=list)
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)
    id: int = 0

    @property
    def message_count(self) -> int:
        return len(self.messages)


# --------------------------------------------------------------------------------------------- rapor + analiz


@dataclass(slots=True)
class Report:
    """Kullanıcının yüklediği teknik rapor. `READY` olunca analiz edilebilir."""

    user_id: int
    title: str
    original_filename: str
    report_type: ReportType
    status: ReportStatus = ReportStatus.UPLOADED
    file_size_kb: float = 0.0
    page_count: int | None = None
    analysis_count: int = 0
    error_message: str | None = None
    uploaded_at: datetime = field(default_factory=utc_now)
    processed_at: datetime | None = None
    file_path: str | None = field(default=None, repr=False)
    id: int = 0


@dataclass(frozen=True, slots=True)
class ComplianceResult:
    """`LLMClient.analyze` sonucu: karar, güven ve gerekçe (henüz kaydedilmemiş)."""

    verdict: ComplianceVerdict
    confidence: float
    reasoning: str


@dataclass(slots=True)
class Analysis:
    """Kaydedilmiş bir uyumluluk analizi."""

    report_id: int
    user_id: int
    query: str
    verdict: ComplianceVerdict
    confidence: float
    reasoning: str
    sources: list[Source] = field(default_factory=list)
    model: str = ""
    duration_ms: int = 0
    created_at: datetime = field(default_factory=utc_now)
    id: int = 0


# --------------------------------------------------------------------------------------------- dosya


@dataclass(frozen=True, slots=True)
class StoredFile:
    """`FileStorage.save_pdf` sonucu: diskteki yol (uuid adlı) ve boyut."""

    path: str
    size_bytes: int
