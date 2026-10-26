"""Bellek-içi repository'ler: `src/domain/interfaces.py`'deki repository arayüzlerinin geçici implementasyonu.

Ne işe yarar: Veritabanı yokken uygulama uçtan uca çalışsın diye kayıtları basit bir `dict`'te tutar
(uygulama kapanınca silinir). Id'ler 1'den artan tam sayıdır. Filtreleme ve sayfalama da burada yapılır;
böylece PostgreSQL'e geçince bu iş SQL'e (`WHERE`, `OFFSET/LIMIT`) taşınır, servisler değişmez.

Thread-safe değildir; tek süreçli demo/geliştirme için yeterli.
TODO(Doruk): Aynı metot imzalarıyla PostgreSQL implementasyonu (ör. `infrastructure/postgres/`), sonra
`src/core/deps.py` içindeki `init_app_state`'te bu sınıfların yerine o sınıflar oluşturulur.
"""

import unicodedata
from collections.abc import Iterable

from src.domain.entities import Analysis, Conversation, Message, Report, Standard, User, utc_now
from src.domain.enums import IndexStatus, ReportStatus, ReportType, StandardStatus, StandardType


def _paginate[T](items: list[T], offset: int, limit: int) -> tuple[list[T], int]:
    """Listeden bir sayfa keser ve toplam sayıyla birlikte döner."""
    return items[offset:offset + limit], len(items)


def _fold(text: str) -> str:
    """Arama için sadeleştirme: Türkçe dahil büyük/küçük harf ve aksan duyarsız.

    `str.casefold()` tek başına yetmez: "İ" → "i" + birleştirici nokta (U+0307) olur, "TİTREŞİM" "titreşim"i bulamaz.
    Bu yüzden NFKD ile harf + işaret ayrılır, işaretler atılır ve noktasız "ı" da "i" sayılır:
    "TİTREŞİM", "Titreşim", "titresim" → "titresim"; "MIL-STD" / "mil-std" → "mil-std".
    """
    decomposed = unicodedata.normalize("NFKD", text)
    stripped = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return stripped.casefold().replace("ı", "i")


def _contains(needle: str | None, *haystacks: str | None) -> bool:
    """Türkçe duyarlı, büyük/küçük harf duyarsız "içeriyor mu" (needle boşsa her şey eşleşir)."""
    if not needle:
        return True
    n = _fold(needle)
    return any(h is not None and n in _fold(h) for h in haystacks)


class _IdCounter:
    """1'den başlayan artan id üretici."""

    def __init__(self) -> None:
        self._last = 0

    def next(self) -> int:
        self._last += 1
        return self._last


class InMemoryStandardRepository:
    """Standart kataloğu (bellekte)."""

    def __init__(self) -> None:
        self._items: dict[int, Standard] = {}
        self._ids = _IdCounter()

    def find(self, *, q: str | None, standard_type: StandardType | None, status: StandardStatus | None,
             index_status: IndexStatus | None, offset: int, limit: int) -> tuple[list[Standard], int]:
        matches = [
            s for s in self._sorted(self._items.values())
            if _contains(q, s.code, s.title)
            and (standard_type is None or s.standard_type == standard_type)
            and (status is None or s.status == status)
            and (index_status is None or s.index_status == index_status)
        ]
        return _paginate(matches, offset, limit)

    def get(self, standard_id: int) -> Standard | None:
        return self._items.get(standard_id)

    def get_by_code(self, code: str) -> Standard | None:
        key = code.strip().casefold()
        return next((s for s in self._items.values() if s.code.casefold() == key), None)

    def list_ids_by_index_status(self, index_status: IndexStatus) -> list[int]:
        return [s.id for s in self._sorted(self._items.values()) if s.index_status == index_status]

    def add(self, standard: Standard) -> Standard:
        standard.id = self._ids.next()
        self._items[standard.id] = standard
        return standard

    def update(self, standard: Standard) -> Standard:
        standard.updated_at = utc_now()
        self._items[standard.id] = standard
        return standard

    @staticmethod
    def _sorted(items: Iterable[Standard]) -> list[Standard]:
        return sorted(items, key=lambda s: s.id)


class InMemoryConversationRepository:
    """Sohbetler ve mesajlar (bellekte). Mesaj id'leri tüm sohbetlerde tekildir."""

    def __init__(self) -> None:
        self._items: dict[int, Conversation] = {}
        self._ids = _IdCounter()
        self._message_ids = _IdCounter()

    def add(self, conversation: Conversation) -> Conversation:
        conversation.id = self._ids.next()
        self._items[conversation.id] = conversation
        return conversation

    def get(self, conversation_id: int) -> Conversation | None:
        return self._items.get(conversation_id)

    def add_message(self, conversation: Conversation, message: Message) -> Message:
        message.id = self._message_ids.next()
        message.conversation_id = conversation.id
        conversation.messages.append(message)
        conversation.updated_at = message.created_at
        return message

    def list_by_user(self, user_id: int, *, offset: int, limit: int) -> tuple[list[Conversation], int]:
        mine = [c for c in self._items.values() if c.user_id == user_id]
        mine.sort(key=lambda c: (c.updated_at, c.id), reverse=True)
        return _paginate(mine, offset, limit)


class InMemoryReportRepository:
    """Kullanıcı raporları (bellekte)."""

    def __init__(self) -> None:
        self._items: dict[int, Report] = {}
        self._ids = _IdCounter()

    def add(self, report: Report) -> Report:
        report.id = self._ids.next()
        self._items[report.id] = report
        return report

    def get(self, report_id: int) -> Report | None:
        return self._items.get(report_id)

    def update(self, report: Report) -> Report:
        self._items[report.id] = report
        return report

    def list_by_user(self, user_id: int, *, status: ReportStatus | None, report_type: ReportType | None,
                     q: str | None, offset: int, limit: int) -> tuple[list[Report], int]:
        mine = [
            r for r in self._items.values()
            if r.user_id == user_id
            and (status is None or r.status == status)
            and (report_type is None or r.report_type == report_type)
            and _contains(q, r.title, r.original_filename)
        ]
        mine.sort(key=lambda r: (r.uploaded_at, r.id), reverse=True)
        return _paginate(mine, offset, limit)


class InMemoryAnalysisRepository:
    """Uyumluluk analizleri (bellekte)."""

    def __init__(self) -> None:
        self._items: dict[int, Analysis] = {}
        self._ids = _IdCounter()

    def add(self, analysis: Analysis) -> Analysis:
        analysis.id = self._ids.next()
        self._items[analysis.id] = analysis
        return analysis

    def get(self, analysis_id: int) -> Analysis | None:
        return self._items.get(analysis_id)


class InMemoryUserRepository:
    """Kullanıcı hesapları (bellekte). `User` değişmez (frozen) olduğu için id ile yeniden oluşturulur."""

    def __init__(self) -> None:
        self._items: dict[int, User] = {}
        self._ids = _IdCounter()

    def add(self, user: User) -> User:
        stored = User(id=self._ids.next(), email=user.email, full_name=user.full_name, role=user.role,
                      created_at=user.created_at, password_hash=user.password_hash)
        self._items[stored.id] = stored
        return stored

    def get(self, user_id: int) -> User | None:
        return self._items.get(user_id)

    def get_by_email(self, email: str) -> User | None:
        key = email.strip().casefold()
        return next((u for u in self._items.values() if u.email.casefold() == key), None)
