"""Arama uygulama servisi (`POST /api/v1/search`) — sohbet ve analiz de kaynak bulmak için bunu kullanır.

Adı bilerek `RetrievalService`: `SearchService` arayüzün (arama motorunun) adı; bu sınıf ise motoru kullanan
iş kuralıdır. Kuralları:
- `standard_ids` boşsa tüm **indekslenmiş** standartlarda aranır; doluysa sadece indekslenmiş olanlar kalır
  (DO-178C gibi PDF'i olmayan standart aranmaz). Aranacak standart kalmazsa motor hiç çağrılmaz, boş liste döner.
- Motor istenen modu desteklemiyorsa `semantic`'e düşülür ve cevapta fiilen kullanılan mod gösterilir.
- Süre (`duration_ms`) burada ölçülür.
"""

import time
from dataclasses import dataclass

from src.domain.entities import Source
from src.domain.enums import IndexStatus, SearchMode
from src.domain.interfaces import SearchService, StandardRepository


@dataclass(frozen=True, slots=True)
class SearchOutcome:
    """Arama sonucu (`SearchResponse` şemasına birebir dönüşür)."""

    query: str
    mode: SearchMode
    results: list[Source]
    duration_ms: int


class RetrievalService:
    """Arama kurallarını uygular, asıl aramayı `SearchService` arayüzüne bırakır."""

    def __init__(self, standards: StandardRepository, search: SearchService) -> None:
        self._standards = standards
        self._search = search

    def search(self, query: str, standard_ids: list[int], top_k: int, mode: SearchMode) -> SearchOutcome:
        started = time.perf_counter()
        effective_mode = mode if self._search.supports(mode) else SearchMode.SEMANTIC
        searchable = self._searchable_ids(standard_ids)
        results = self._search.search(query, searchable, top_k, effective_mode) if searchable else []
        return SearchOutcome(query=query, mode=effective_mode, results=results, duration_ms=_elapsed_ms(started))

    def existing_standard_ids(self, standard_ids: list[int]) -> list[int]:
        """Verilen id'lerden katalogda gerçekten var olanlar (sıralı, tekrarsız). Sohbet kaydı bunu kullanır."""
        return sorted({sid for sid in standard_ids if self._standards.get(sid) is not None})

    def _searchable_ids(self, requested: list[int]) -> list[int]:
        indexed = self._standards.list_ids_by_index_status(IndexStatus.INDEXED)
        if not requested:
            return indexed
        wanted = set(requested)
        return [standard_id for standard_id in indexed if standard_id in wanted]


def _elapsed_ms(started: float) -> int:
    """`time.perf_counter()` ile alınmış başlangıçtan bu yana geçen milisaniye."""
    return int((time.perf_counter() - started) * 1000)
