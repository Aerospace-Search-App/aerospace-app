"""Mock arama: `SearchService` arayüzünün geçici, **deterministik** implementasyonu.

Ne işe yarar: Gerçek hibrit arama (vektör + anahtar kelime) yokken mobil ekip gerçekçi kaynak kartları görsün diye
küçük, elle yazılmış bir sahte parça kataloğu tutar (MIL-STD-810H Method 514.8 Vibration s.412 gibi).
Aynı sorgu → hep aynı sonuç ve puan (demo ve testler tekrarlanabilir olsun).

Nasıl puanlar: Sorgu küçük harfe çevrilir, Türkçe karakterler sadeleşir, kelimeler basit bir Türkçe→İngilizce
sözlükle ("vibrasyon" → "vibration", "sıcaklık" → "temperature") genişletilir; her parçanın anahtar kelimeleriyle
eşleşme sayısına göre 0–1 arası puan verilir. Hiç eşleşme yoksa seçili standartların parçaları sabit sırayla,
düşük puanla döner (demo her zaman kaynak görsün). Seçili standartlarda hiç parça yoksa boş liste döner.

TODO(Sudenur): madde bazlı parçalama + hibrit arama (ChromaDB/pgvector + BM25). Aynı arayüzle yazılıp
`src/core/deps.py`'de `SEARCH_PROVIDER` ile seçilecek; servisler ve router'lar değişmez.
"""

import re
import unicodedata
from collections.abc import Callable
from dataclasses import dataclass

from loguru import logger

from src.domain.entities import IndexResult, Source
from src.domain.enums import SearchMode


@dataclass(frozen=True, slots=True)
class _ChunkSpec:
    """Katalogdaki sahte parçanın şablonu (standart id'si seed sırasında verilir)."""

    number: int
    section: str
    page: int
    snippet: str
    keywords: frozenset[str]
    requirement_id: int | None = None


def _spec(number: int, section: str, page: int, keywords: str, snippet: str, req: int | None = None) -> _ChunkSpec:
    return _ChunkSpec(number, section, page, snippet, frozenset(keywords.split()), req)


# Gerçek standartlardaki bölüm adları ve yaklaşık sayfalarıyla sahte parçalar (metinler kısaltılmış ifadelerdir).
SEED_CATALOG: dict[str, list[_ChunkSpec]] = {
    "MIL-STD-810H": [
        _spec(42, "Method 514.8", 412, "vibration test duration axis profile",
              "The test item shall be subjected to the vibration levels and durations specified in Table "
              "514.8-I for each of the three orthogonal axes.", 10),
        _spec(47, "Method 514.8", 418, "vibration duration axis hours random",
              "Unless otherwise specified, conduct the random vibration test for a minimum of one hour "
              "per axis.", 11),
        _spec(101, "Method 501.7", 98, "temperature high heat storage operation",
              "Expose the test item to the high temperature storage cycle for a minimum of seven 24-hour "
              "cycles, then verify operation at the operating high temperature.", 20),
        _spec(115, "Method 502.7", 140, "temperature low cold storage operation",
              "Stabilize the test item at the low storage temperature for at least four hours before "
              "operational checks.", 21),
        _spec(168, "Method 507.6", 268, "humidity moisture temperature cycle",
              "Subject the test item to a minimum of ten 24-hour cycles of the aggravated humidity "
              "profile (95% RH).", 30),
        _spec(201, "Method 500.6", 60, "pressure altitude low air",
              "Reduce the chamber pressure to the equivalent of the specified operational altitude and "
              "maintain for at least one hour.", 40),
        _spec(230, "Method 516.8", 560, "shock impact pulse drop",
              "Apply three shocks in each direction along each of three orthogonal axes using the "
              "functional shock pulse defined in Table 516.8-VI.", 50),
        _spec(290, "Method 510.7", 330, "sand dust particle blowing",
              "Expose the test item to blowing dust at a concentration of 10.6 ± 7 g/m³ for six hours "
              "per exposed face.", 60),
    ],
    "MIL-STD-461G": [
        _spec(12, "CE102", 48, "conducted emissions power leads",
              "Conducted emissions on power leads shall not exceed the limits shown in Figure CE102-1 "
              "from 10 kHz to 10 MHz.", 410),
        _spec(22, "CS101", 60, "conducted susceptibility power leads",
              "The equipment shall not exhibit any malfunction when subjected to the CS101 voltage "
              "limit on power leads.", 420),
        _spec(31, "RE102", 98, "radiated emissions electric field",
              "Electric field emissions shall not be radiated in excess of the limits shown in Figures "
              "RE102-1 through RE102-4 from 10 kHz to 18 GHz.", 430),
        _spec(38, "CS114", 88,
              "conducted susceptibility cable injection",
              "The equipment shall not exhibit any malfunction when subjected to bulk cable injection "
              "levels per Figure CS114-1.", 440),
        _spec(45, "RS103", 130, "radiated susceptibility electric field",
              "The equipment shall not exhibit any malfunction when subjected to the radiated electric "
              "fields listed in Table VIII from 2 MHz to 40 GHz.", 450),
    ],
}

# Yeni bir PDF indekslendiğinde o standart için üretilecek genel sahte parçalar.
_GENERIC_SECTIONS: list[tuple[str, int, str, str]] = [
    ("1. Scope", 1, "scope general purpose", "This document establishes the scope and applicability of the standard."),
    ("3. Definitions", 3, "definitions terms", "The terms used in this document are defined in this section."),
    ("4. General Requirements", 5, "general requirements",
     "The equipment shall meet the general requirements of this section before detailed tests."),
    ("5. Detailed Requirements", 8, "detailed requirements verification",
     "Detailed requirements and verification methods are specified in the following subsections."),
]

# Basit Türkçe → İngilizce eşleme (anahtarlar Türkçe karakterleri sadeleştirilmiş kök halidir; kelime bu kökle
# başlıyorsa eşleşir, ör. "titreşimi" → "titresim" → vibration).
_TR_EN: dict[str, tuple[str, ...]] = {
    "vibrasyon": ("vibration",), "titresim": ("vibration",), "sure": ("duration", "hours"),
    "saat": ("hours", "duration"), "eksen": ("axis",), "sicaklik": ("temperature",), "isi": ("temperature", "heat"),
    "yuksek": ("high",), "dusuk": ("low",), "soguk": ("cold", "low", "temperature"),
    "sicak": ("heat", "high", "temperature"), "nem": ("humidity", "moisture"), "sok": ("shock",),
    "darbe": ("shock", "impact"), "dusme": ("drop", "shock"), "basinc": ("pressure",), "irtifa": ("altitude",),
    "yukseklik": ("altitude",), "kum": ("sand",), "toz": ("dust",), "emisyon": ("emissions",),
    "yayim": ("emissions",), "isinim": ("radiated",), "yayilim": ("radiated",), "iletim": ("conducted",),
    "iletilen": ("conducted",), "bagisiklik": ("susceptibility",), "duyarlilik": ("susceptibility",),
    "kablo": ("cable",), "guc": ("power",), "elektrik": ("electric",), "alan": ("field",),
    "depolama": ("storage",), "calisma": ("operation",), "kapsam": ("scope",), "gereksinim": ("requirements",),
    "tanim": ("definitions",),
}
_ASCII = str.maketrans("ıİşŞğĞüÜöÖçÇ", "iissgguuoocc")
_MATCH_BASE, _MATCH_STEP, _MATCH_MAX = 0.55, 0.12, 0.97
_FALLBACK_BASE, _FALLBACK_STEP, _FALLBACK_MIN = 0.15, 0.01, 0.05


def _terms(query: str) -> set[str]:
    """Sorguyu sadeleştirilmiş kelimelere ayırır ve Türkçe kökleri İngilizce karşılıklarıyla genişletir."""
    text = unicodedata.normalize("NFC", query).translate(_ASCII).lower()
    words = {w for w in re.split(r"[^a-z0-9]+", text) if len(w) >= 2}
    expanded = set(words)
    for word in words:
        for root, english in _TR_EN.items():
            if _root_matches(word, root):
                expanded.update(english)
    return expanded


def _root_matches(word: str, root: str) -> bool:
    """Kelime kökle başlıyor mu? Kısa köklerde (nem, şok, ısı) sadece kısa ekler kabul edilir ("ışınım" ısı değil)."""
    max_suffix = 2 if len(root) <= 3 else 6
    return word.startswith(root) and len(word) - len(root) <= max_suffix


def _hits(terms: set[str], keywords: frozenset[str]) -> int:
    """Parçanın kaç anahtar kelimesi sorguda geçiyor ("vibrations" → "vibration" da sayılır)."""
    return sum(1 for k in keywords if any(t == k or (len(k) >= 4 and t.startswith(k)) for t in terms))


class MockSearchService:
    """Sahte parça kataloğu üzerinde deterministik arama."""

    name = "mock"

    def __init__(self, page_counter: Callable[[str], int]) -> None:
        # page_counter: yüklenen PDF'in sayfa sayısını bulan fonksiyon (FileStorage.count_pages).
        self._page_counter = page_counter
        self._chunks: dict[int, list[tuple[_ChunkSpec, str]]] = {}  # standard_id → [(şablon, standart kodu)]

    def load_seed_catalog(self, standard_id: int, standard_code: str) -> None:
        """Seed sırasında hazır indekslenmiş standartların sahte parçalarını yükler."""
        self._chunks[standard_id] = [(spec, standard_code) for spec in SEED_CATALOG.get(standard_code, [])]

    def supports(self, mode: SearchMode) -> bool:
        return True  # mock her modu aynı şekilde "destekler"

    def search(self, query: str, standard_ids: list[int], top_k: int, mode: SearchMode) -> list[Source]:
        candidates = [
            (standard_id, spec, code)
            for standard_id in sorted(set(standard_ids))
            for spec, code in self._chunks.get(standard_id, [])
        ]
        terms = _terms(query)
        scored: list[tuple[float, int, Source]] = []
        fallback_rank = 0
        for order, (standard_id, spec, code) in enumerate(candidates):
            hits = _hits(terms, spec.keywords)
            if hits:
                score = min(_MATCH_MAX, _MATCH_BASE + _MATCH_STEP * hits)
            else:
                score = max(_FALLBACK_MIN, _FALLBACK_BASE - _FALLBACK_STEP * fallback_rank)
                fallback_rank += 1
            scored.append((round(score, 2), order, self._to_source(standard_id, code, spec, round(score, 2))))
        scored.sort(key=lambda item: (-item[0], item[1]))
        return [source for _, _, source in scored[:top_k]]

    def index_document(self, standard_id: int, standard_code: str, file_path: str) -> IndexResult:
        page_count = self._page_counter(file_path)
        specs = SEED_CATALOG.get(standard_code) or [
            _spec(i + 1, section, min(page, page_count), keywords, snippet)
            for i, (section, page, keywords, snippet) in enumerate(_GENERIC_SECTIONS)
        ]
        self._chunks[standard_id] = [(spec, standard_code) for spec in specs]
        logger.debug("Mock indeks: {} için {} parça", standard_code, len(specs))
        return IndexResult(page_count=page_count, chunk_count=page_count * 5,
                           requirement_count=max(1, page_count // 4))

    @staticmethod
    def _to_source(standard_id: int, code: str, spec: _ChunkSpec, score: float) -> Source:
        return Source(
            chunk_id=f"std_{standard_id}_chunk_{spec.number:04d}", standard_id=standard_id, standard_code=code,
            requirement_id=spec.requirement_id, section=spec.section, page=spec.page, snippet=spec.snippet,
            score=score,
        )
