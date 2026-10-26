"""Mock dil modeli: `LLMClient` arayüzünün geçici, **deterministik** implementasyonları.

- `MockLLMClient`: Gemini yokken cevap üretir. Cevaplar her zaman `[DEMO]` ile başlar (gerçek sanılmasın) ve
  kaynak gösterir: "[DEMO] MIL-STD-810H · Method 514.8 (Sayfa 412) kaynağına göre: ...". Aynı girdi → aynı çıktı.
  Analizde sözleşme §6 gereği hep `INSUFFICIENT`, güven `0.5` döner.
- `UnavailableLLMClient`: `LLM_PROVIDER` henüz bağlanmamış bir değerse (ör. "gemini") kullanılır; her çağrıda
  `LLMError` fırlatır. Böylece uygulama yine açılır, sohbet `LLM_UNAVAILABLE`, analiz 503 döner.

TODO: Gerçek Gemini istemcisi (`google-genai`, model adı `GEMINI_MODEL` ayarından; kaydedilen = çağrılan model).
"""

from src.domain.entities import ComplianceResult, Source
from src.domain.enums import ComplianceVerdict
from src.domain.interfaces import LLMError

MOCK_MODEL_NAME = "mock-llm"
_MAX_EXTRA_SOURCES = 2


def _cite(source: Source) -> str:
    """Kaynak etiketi: "MIL-STD-810H · Method 514.8 (Sayfa 412)"."""
    parts = [source.standard_code] + ([source.section] if source.section else [])
    page = f" (Sayfa {source.page})" if source.page else ""
    return " · ".join(parts) + page


class MockLLMClient:
    """Şablonla, kaynaklardan cevap/karar üreten sahte model."""

    @property
    def model_name(self) -> str:
        return MOCK_MODEL_NAME

    def answer(self, question: str, sources: list[Source]) -> str:
        if not sources:
            return "[DEMO] Bu soru için seçili standartlarda ilgili bir bölüm bulunamadı."
        best, extra = sources[0], sources[1:1 + _MAX_EXTRA_SOURCES]
        text = f"[DEMO] {_cite(best)} kaynağına göre: \"{best.snippet}\""
        if extra:
            text += " İlgili diğer kaynaklar: " + "; ".join(_cite(s) for s in extra) + "."
        return text

    def analyze(self, query: str, report_text: str, sources: list[Source]) -> ComplianceResult:
        basis = (f"Karşılaştırılan en ilgili madde: {_cite(sources[0])}." if sources
                 else "Seçili standartlarda karşılaştırılacak madde bulunamadı.")
        return ComplianceResult(
            verdict=ComplianceVerdict.INSUFFICIENT,
            confidence=0.5,
            reasoning="[DEMO] Mock modda rapor gerçek bir dil modeliyle değerlendirilmedi; karar "
                      f"'Yetersiz Bilgi' olarak işaretlendi. {basis}",
        )


class UnavailableLLMClient:
    """Henüz bağlanmamış sağlayıcı için yer tutucu: her çağrıda anlaşılır bir `LLMError` fırlatır."""

    def __init__(self, provider: str) -> None:
        self._provider = provider

    @property
    def model_name(self) -> str:
        return self._provider

    def answer(self, question: str, sources: list[Source]) -> str:
        raise LLMError(f"LLM_PROVIDER={self._provider} henüz bağlanmadı.")

    def analyze(self, query: str, report_text: str, sources: list[Source]) -> ComplianceResult:
        raise LLMError(f"LLM_PROVIDER={self._provider} henüz bağlanmadı.")
