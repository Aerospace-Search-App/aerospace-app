"""Arama şemaları (sözleşme §5) — `POST /api/v1/search` ve ortak `SourceOut`.

`SourceOut`, RAG'ın bulduğu her metin parçasıdır; arama, sohbet ve rapor analizi cevaplarında **aynı** şema
kullanılır. Böylece mobil ekip tek bir "kaynak kartı" bileşeni yazar.
Gerçek arama motoru (hibrit arama) Sudenur'un `SearchService` implementasyonundan gelecek; şema değişmez.
"""

from pydantic import BaseModel, ConfigDict, Field

from src.domain.enums import SearchMode

# Sözleşme §5: top_k 1–20, varsayılan 5 (meta/enums `limits.max_top_k` ile aynı değer).
MAX_TOP_K = 20
DEFAULT_TOP_K = 5

SOURCE_EXAMPLE = {
    "chunk_id": "std_1_chunk_0042",
    "standard_id": 1,
    "standard_code": "MIL-STD-810H",
    "requirement_id": 10,
    "section": "Method 514.8",
    "page": 412,
    "snippet": "The test item shall be subjected to the vibration levels and durations specified in Table 514.8-I.",
    "score": 0.87,
}


class SourceOut(BaseModel):
    """Bir kaynak parça: hangi standardın hangi bölümü/sayfası, metinden kesit ve benzerlik puanı."""

    model_config = ConfigDict(from_attributes=True, json_schema_extra={"examples": [SOURCE_EXAMPLE]})

    chunk_id: str = Field(..., description="Parçanın benzersiz kimliği.", examples=["std_1_chunk_0042"])
    standard_id: int = Field(..., description="Parçanın ait olduğu standart.", examples=[1])
    standard_code: str = Field(..., description="Standart kodu.", examples=["MIL-STD-810H"])
    requirement_id: int | None = Field(default=None, description="Eşleşen gereksinim (madde) varsa kimliği.",
                                       examples=[10])
    section: str | None = Field(default=None, description="Bölüm/madde adı.", examples=["Method 514.8"])
    page: int | None = Field(default=None, ge=1, description="PDF sayfa numarası (görüntüleyicide atlamak için).",
                             examples=[412])
    snippet: str = Field(..., description="Parçadan kısa metin kesiti.", examples=[SOURCE_EXAMPLE["snippet"]])
    score: float = Field(..., ge=0, le=1, description="Benzerlik puanı (0–1, yüksek = daha ilgili).",
                         examples=[0.87])


class SearchRequest(BaseModel):
    """`POST /api/v1/search` gövdesi: LLM'siz ham arama."""

    model_config = ConfigDict(str_strip_whitespace=True, json_schema_extra={"examples": [
        {"query": "vibrasyon testi süresi", "standard_ids": [1], "top_k": 5, "mode": "hybrid"},
    ]})

    query: str = Field(..., min_length=2, max_length=500, description="Arama metni (2–500 karakter).",
                       examples=["vibrasyon testi süresi"])
    standard_ids: list[int] = Field(default_factory=list,
                                    description="Aranacak standartlar. Boş liste = tüm indekslenmiş standartlar.",
                                    examples=[[1]])
    top_k: int = Field(default=DEFAULT_TOP_K, ge=1, le=MAX_TOP_K, description="Dönecek sonuç sayısı (1–20).",
                       examples=[5])
    mode: SearchMode = Field(default=SearchMode.HYBRID,
                             description="Arama modu. Desteklenmiyorsa servis `semantic`'e düşer.",
                             examples=["hybrid"])


class SearchResponse(BaseModel):
    """Arama cevabı. `mode` fiilen kullanılan modu gösterir (düşme olduysa `semantic`)."""

    model_config = ConfigDict(from_attributes=True, json_schema_extra={"examples": [{
        "query": "vibrasyon testi süresi", "mode": "hybrid", "results": [SOURCE_EXAMPLE], "duration_ms": 42,
    }]})

    query: str = Field(..., description="Gönderilen arama metni.", examples=["vibrasyon testi süresi"])
    mode: SearchMode = Field(..., description="Kullanılan arama modu.", examples=["hybrid"])
    results: list[SourceOut] = Field(..., description="Puanı yüksekten düşüğe sıralı sonuçlar.",
                                     examples=[[SOURCE_EXAMPLE]])
    duration_ms: int = Field(..., ge=0, description="Aramanın süresi (milisaniye).", examples=[42])
