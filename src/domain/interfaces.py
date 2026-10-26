"""Arayüzler (Protocol): servislerin dış dünyadan beklediği "prizler".

Ne işe yarar: Servisler "veriyi PostgreSQL'e mi yazıyorum, belleğe mi?", "arama ChromaDB ile mi, sahte mi?"
diye bilmez; sadece buradaki arayüzü çağırır. Hangi implementasyonun takılacağı `src/core/deps.py`'de seçilir.

Benzetme: Duvardaki priz gibi. Priz (arayüz) sabittir; ona bugün bir test lambası (mock), yarın gerçek cihaz
(PostgreSQL, hibrit arama, Gemini) takılır. Prizin arkasındaki kabloyu (servisleri) değiştirmek gerekmez.

`typing.Protocol` kullanıldığı için implementasyonlar bu sınıflardan miras almak zorunda değildir;
aynı metotlara sahip olmaları yeterlidir ("ördek gibi yürüyorsa ördektir").
"""

from typing import BinaryIO, Protocol

from src.domain.entities import (
    Analysis,
    ComplianceResult,
    Conversation,
    IndexResult,
    Message,
    Report,
    Source,
    Standard,
    StoredFile,
    User,
)
from src.domain.enums import IndexStatus, ReportStatus, ReportType, SearchMode, StandardStatus, StandardType


class LLMError(Exception):
    """Dil modeli cevap üretemedi (anahtar yok, kota, ağ hatası...). Servisler bunu yakalayıp
    sohbette `LLM_UNAVAILABLE` durumuna, analizde 503'e çevirir."""


# --------------------------------------------------------------------------------------------- repository'ler
# Şimdi: src/infrastructure/memory/repositories.py (bellek-içi, uygulama kapanınca silinir).
# TODO(Doruk): PostgreSQL implementasyonu — aynı metot imzalarıyla; deps.py'de tek satır değişir.


class StandardRepository(Protocol):
    """Standart kataloğunun deposu. Filtreleme ve sayfalama burada yapılır (DB'de SQL ile yapılacak)."""

    def find(self, *, q: str | None, standard_type: StandardType | None, status: StandardStatus | None,
             index_status: IndexStatus | None, offset: int, limit: int) -> tuple[list[Standard], int]:
        """Filtreye uyan standartlar (id sırasıyla) ve toplam sayı. `q` kod/başlıkta, büyük-küçük harf duyarsız."""
        ...

    def get(self, standard_id: int) -> Standard | None: ...

    def get_by_code(self, code: str) -> Standard | None:
        """Kodla bul (büyük/küçük harf duyarsız)."""
        ...

    def list_ids_by_index_status(self, index_status: IndexStatus) -> list[int]:
        """Belirli indeks durumundaki standartların id'leri (ör. aramaya hazır olanlar)."""
        ...

    def add(self, standard: Standard) -> Standard:
        """Yeni kayıt; id'yi atar ve kaydı döner."""
        ...

    def update(self, standard: Standard) -> Standard: ...


class ConversationRepository(Protocol):
    """Sohbetlerin ve mesajların deposu."""

    def add(self, conversation: Conversation) -> Conversation: ...

    def get(self, conversation_id: int) -> Conversation | None: ...

    def add_message(self, conversation: Conversation, message: Message) -> Message:
        """Mesaja id verir, sohbete ekler, sohbetin `updated_at`'ini günceller."""
        ...

    def list_by_user(self, user_id: int, *, offset: int, limit: int) -> tuple[list[Conversation], int]:
        """Kullanıcının sohbetleri, en yeni (son güncellenen) önce."""
        ...


class ReportRepository(Protocol):
    """Kullanıcı raporlarının deposu. Listeleme her zaman kullanıcıya göre filtrelenir."""

    def add(self, report: Report) -> Report: ...

    def get(self, report_id: int) -> Report | None: ...

    def update(self, report: Report) -> Report: ...

    def list_by_user(self, user_id: int, *, status: ReportStatus | None, report_type: ReportType | None,
                     q: str | None, offset: int, limit: int) -> tuple[list[Report], int]:
        """Kullanıcının raporları, en yeni önce. `q` başlıkta/dosya adında arar."""
        ...


class AnalysisRepository(Protocol):
    """Uyumluluk analizlerinin deposu."""

    def add(self, analysis: Analysis) -> Analysis: ...

    def get(self, analysis_id: int) -> Analysis | None: ...


class UserRepository(Protocol):
    """Kullanıcı hesaplarının deposu (Taha'nın auth modülü kullanır)."""

    def add(self, user: User) -> User: ...

    def get(self, user_id: int) -> User | None: ...

    def get_by_email(self, email: str) -> User | None:
        """E-postayla bul (büyük/küçük harf duyarsız)."""
        ...


# --------------------------------------------------------------------------------------------- arama


class SearchService(Protocol):
    """Standart PDF'lerini parçalara bölüp indeksleyen ve sorguya en ilgili parçaları bulan motor (RAG'ın "R"si).

    Şimdi: `src/infrastructure/search/mock_search.py` (sabit, gerçekçi sahte parça kataloğu).
    TODO(Sudenur): madde bazlı parçalama + hibrit arama (anlamsal + anahtar kelime) implementasyonu.
    """

    @property
    def name(self) -> str:
        """Sağlayıcı adı (`/health` cevabında görünür), ör. "mock"."""
        ...

    def supports(self, mode: SearchMode) -> bool:
        """Bu arama modunu destekliyor mu? Desteklemiyorsa uygulama `semantic`'e düşer."""
        ...

    def search(self, query: str, standard_ids: list[int], top_k: int, mode: SearchMode) -> list[Source]:
        """`standard_ids` içindeki standartlarda arar; puanı yüksekten düşüğe en fazla `top_k` parça döner.

        Hangi standartların aranabilir (INDEXED) olduğuna uygulama servisi karar verir; buraya hep dolu,
        filtrelenmiş bir liste gelir.
        """
        ...

    def index_document(self, standard_id: int, standard_code: str, file_path: str) -> IndexResult:
        """PDF'i parçalara bölüp indeksler (uzun sürebilir; arka planda çağrılır). Hata olursa exception fırlatır."""
        ...


# --------------------------------------------------------------------------------------------- LLM


class LLMClient(Protocol):
    """Kaynak parçalardan cevap ve uyumluluk kararı üreten dil modeli (RAG'ın "G"si).

    Şimdi: `src/infrastructure/llm/mock_llm.py` (`[DEMO]` ile başlayan deterministik cevaplar).
    Gerçeği: Gemini (`GEMINI_MODEL` ayarı). Cevap üretemezse `LLMError` fırlatır.
    """

    @property
    def model_name(self) -> str:
        """Gerçekte çağrılan modelin adı; cevaplara ve analiz kayıtlarına bu yazılır."""
        ...

    def answer(self, question: str, sources: list[Source]) -> str:
        """Soruyu yalnızca verilen kaynaklara dayanarak, kaynak göstererek cevaplar."""
        ...

    def analyze(self, query: str, report_text: str, sources: list[Source]) -> ComplianceResult:
        """Rapor metnini standart parçalarıyla karşılaştırıp karar verir."""
        ...


# --------------------------------------------------------------------------------------------- dosya deposu


class FileStorage(Protocol):
    """Yüklenen PDF'lerin saklandığı yer.

    Şimdi: `src/infrastructure/storage/local_storage.py` (yerel `STORAGE_DIR` klasörü).
    İleride: bulut depolama (S3 vb.) aynı arayüzle takılabilir.
    """

    def save_pdf(self, stream: BinaryIO, filename: str | None) -> StoredFile:
        """PDF'i doğrular (uzantı, `%PDF` imzası, boyut) ve uuid adla kaydeder.

        Kullanıcının dosya adı diskte **kullanılmaz**. Hatalar: `UnsupportedFileError` (415),
        `PayloadTooLargeError` (413).
        """
        ...

    def count_pages(self, path: str) -> int:
        """PDF'in sayfa sayısı (mock: basit tahmin). TODO(Onur): gerçek PDF okuyucu."""
        ...

    def delete(self, path: str) -> None:
        """Dosyayı siler; yoksa sessizce geçer."""
        ...
