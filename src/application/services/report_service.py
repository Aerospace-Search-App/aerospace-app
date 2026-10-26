"""Rapor servisi: teknik rapor yükleme, arka planda işleme, listeleme ve detay.

Yükleme akışı (eski koddaki H3/H4 hataları tekrarlanmasın):
1. `upload`: dosya `FileStorage` ile doğrulanıp uuid adla kaydedilir (kullanıcının dosya adı sadece gösterim
   için saklanır), kayıt `UPLOADED` olur, endpoint hemen 202 döner.
2. `process` (BackgroundTasks): `PROCESSING` → sayfa sayısı çıkarılır → `READY` (analize hazır).
   Hata olursa `FAILED` + Türkçe `error_message` kaydedilir; kayıt kaybolmaz.

Raporlar kullanıcıya özeldir: listede sadece kendi raporları, başkasının raporu 404.
"""

from pathlib import PurePath
from typing import BinaryIO

from loguru import logger

from src.core.errors import NotFoundError
from src.domain.entities import Report, User, utc_now
from src.domain.enums import ReportStatus, ReportType
from src.domain.interfaces import FileStorage, ReportRepository

_DEFAULT_TITLE = "Adsız Rapor"
_TITLE_MAX_LENGTH = 200
_FILENAME_MAX_LENGTH = 255


def _display_filename(filename: str | None) -> str:
    """Gösterim için dosya adı: klasör kısmı atılır (ör. `C:\\x\\rapor.pdf` → `rapor.pdf`). Diskte kullanılmaz."""
    name = PurePath((filename or "").replace("\\", "/")).name.strip()
    return (name or "rapor.pdf")[:_FILENAME_MAX_LENGTH]


def _title_from_filename(filename: str) -> str:
    """`telsiz_titresim-raporu.pdf` → `telsiz titresim raporu`."""
    stem = filename.rsplit(".", 1)[0].replace("_", " ").replace("-", " ")
    return " ".join(stem.split())[:_TITLE_MAX_LENGTH] or _DEFAULT_TITLE


class ReportService:
    """Rapor yükleme ve işleme iş kuralları."""

    def __init__(self, reports: ReportRepository, storage: FileStorage) -> None:
        self._reports = reports
        self._storage = storage

    def upload(self, user: User, stream: BinaryIO, filename: str | None, title: str | None,
               report_type: ReportType) -> Report:
        stored = self._storage.save_pdf(stream, filename)
        original = _display_filename(filename)
        clean_title = (title or "").strip()[:_TITLE_MAX_LENGTH] or _title_from_filename(original)
        report = self._reports.add(Report(
            user_id=user.id, title=clean_title, original_filename=original, report_type=report_type,
            status=ReportStatus.UPLOADED, file_size_kb=round(stored.size_bytes / 1024, 1), file_path=stored.path,
        ))
        logger.info("Rapor yüklendi: id={} kullanıcı={}", report.id, user.id)
        return report

    def process(self, report_id: int) -> None:
        """Arka plan görevi: raporu analize hazırlar. Exception dışarı sızmaz; sonuç durum alanlarına yazılır."""
        report = self._reports.get(report_id)
        if report is None or report.file_path is None:
            logger.warning("İşlenecek rapor/dosya yok: id={}", report_id)
            return
        report.status = ReportStatus.PROCESSING
        self._reports.update(report)
        try:
            # TODO(Onur/Sudenur): metin çıkarma + raporu parçalama (analizde en ilgili parçalar kullanılacak).
            report.page_count = self._storage.count_pages(report.file_path)
        except Exception:
            logger.exception("Rapor işlenemedi: id={}", report_id)
            report.status = ReportStatus.FAILED
            report.error_message = "Rapor işlenemedi. PDF'in bozuk olmadığından emin olup yeniden yükleyin."
        else:
            report.status = ReportStatus.READY
            logger.info("Rapor hazır: id={} sayfa={}", report_id, report.page_count)
        report.processed_at = utc_now()
        self._reports.update(report)

    def list_reports(self, user: User, *, status: ReportStatus | None, report_type: ReportType | None,
                     q: str | None, offset: int, limit: int) -> tuple[list[Report], int]:
        return self._reports.list_by_user(user.id, status=status, report_type=report_type, q=q,
                                          offset=offset, limit=limit)

    def get(self, user: User, report_id: int) -> Report:
        report = self._reports.get(report_id)
        if report is None or report.user_id != user.id:
            raise NotFoundError(f"Rapor bulunamadı: id={report_id}")
        return report
