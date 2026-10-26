"""Uyumluluk analizi servisi: bir raporu seçilen standartların ilgili maddeleriyle karşılaştırır.

Kurallar (sözleşme §6):
- Rapor yoksa veya başkasınınsa 404; `READY` değilse 409 (önce işlenmesi beklenir).
- İlgili standart parçaları `RetrievalService` ile bulunur, karar `LLMClient.analyze` ile verilir.
- LLM cevap veremezse 503 `LLM_UNAVAILABLE` ve analiz **kaydedilmez** (yarım/yanlış kayıt oluşmaz).
- Başarılıysa analiz kaydedilir, raporun `analysis_count`'u artar ve **kaydedilen nesne** döner
  (eski koddaki H1: kayıt yapılıp tanımsız değişken yüzünden hep 500 dönülüyordu).
"""

import time

from loguru import logger

from src.application.services.report_service import ReportService
from src.application.services.retrieval_service import RetrievalService
from src.core.errors import ConflictError, LLMUnavailableError
from src.domain.entities import Analysis, User
from src.domain.enums import ReportStatus, SearchMode
from src.domain.interfaces import AnalysisRepository, LLMClient, LLMError, ReportRepository


class AnalysisService:
    """Rapor uyumluluk analizi iş kuralları."""

    def __init__(self, analyses: AnalysisRepository, reports: ReportRepository, report_service: ReportService,
                 retrieval: RetrievalService, llm: LLMClient) -> None:
        self._analyses = analyses
        self._reports = reports
        self._report_service = report_service
        self._retrieval = retrieval
        self._llm = llm

    def create(self, user: User, report_id: int, query: str, standard_ids: list[int], top_k: int) -> Analysis:
        started = time.perf_counter()
        report = self._report_service.get(user, report_id)  # yoksa / başkasınınsa 404
        if report.status != ReportStatus.READY:
            raise ConflictError(f"Rapor analize hazır değil (durum: {report.status}). READY olunca tekrar deneyin.")
        sources = self._retrieval.search(query, standard_ids, top_k, SearchMode.HYBRID).results
        # TODO(Sudenur): rapor metni de parçalanıp sorguya en ilgili rapor parçaları verilecek (şimdilik başlık).
        try:
            result = self._llm.analyze(query, report.title, sources)
        except LLMError as exc:
            logger.warning("Analiz yapılamadı (LLM): {}", exc)
            raise LLMUnavailableError("Dil modeli şu anda cevap veremiyor; analiz kaydedilmedi. "
                                      "Daha sonra tekrar deneyin.") from exc
        analysis = self._analyses.add(Analysis(
            report_id=report.id, user_id=user.id, query=query, verdict=result.verdict,
            confidence=result.confidence, reasoning=result.reasoning, sources=sources, model=self._llm.model_name,
            duration_ms=int((time.perf_counter() - started) * 1000),
        ))
        report.analysis_count += 1
        self._reports.update(report)
        logger.info("Analiz kaydedildi: id={} rapor={} karar={}", analysis.id, report.id, analysis.verdict)
        return analysis
