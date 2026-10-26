"""Standart servisi: katalog (liste/ekle/detay), PDF yükleme ve arka planda indeksleme.

Bağımlılıkları arayüzdür: `StandardRepository` (Doruk), `SearchService` (Sudenur), `FileStorage`.
HTTP bilmez; sorun olursa `NotFoundError`, `ConflictError` gibi `AppError`'lar fırlatır.

PDF yükleme akışı (eski koddaki H3/H4/H11 hataları tekrarlanmasın):
1. `upload_document`: önce standart var mı (404) ve indeksleme sürüyor mu (409) bakılır, **sonra** dosya
   kaydedilir → durum `PENDING`, endpoint hemen 202 döner.
2. `index_document` (BackgroundTasks ile, cevap gittikten sonra): `PROCESSING` → arama motoru PDF'i
   indeksler → `INDEXED`. Hata olursa `FAILED` + Türkçe `error_message` kaydedilir; durum kaybolmaz.
"""

from typing import BinaryIO

from loguru import logger

from src.application.schemas.standard import StandardCreate
from src.core.errors import ConflictError, NotFoundError
from src.domain.entities import IndexState, Standard, utc_now
from src.domain.enums import IndexStatus, StandardStatus, StandardType
from src.domain.interfaces import FileStorage, SearchService, StandardRepository

_BUSY = (IndexStatus.PENDING, IndexStatus.PROCESSING)


class StandardsService:
    """Standart kataloğu ve indeksleme iş kuralları."""

    def __init__(self, standards: StandardRepository, search: SearchService, storage: FileStorage) -> None:
        self._standards = standards
        self._search = search
        self._storage = storage

    def list_standards(self, *, q: str | None, standard_type: StandardType | None, status: StandardStatus | None,
             index_status: IndexStatus | None, offset: int, limit: int) -> tuple[list[Standard], int]:
        return self._standards.find(q=q, standard_type=standard_type, status=status,
                                    index_status=index_status, offset=offset, limit=limit)

    def create(self, data: StandardCreate) -> Standard:
        code = data.code.strip()
        if self._standards.get_by_code(code) is not None:
            raise ConflictError(f"Bu kodla bir standart zaten kayıtlı: {code}")
        standard = self._standards.add(Standard(**data.model_dump(exclude={"code"}), code=code))
        logger.info("Standart oluşturuldu: id={} kod={}", standard.id, standard.code)
        return standard

    def get(self, standard_id: int) -> Standard:
        standard = self._standards.get(standard_id)
        if standard is None:
            raise NotFoundError(f"Standart bulunamadı: id={standard_id}")
        return standard

    def get_index_status(self, standard_id: int) -> IndexState:
        return self.get(standard_id).index_state()

    def upload_document(self, standard_id: int, stream: BinaryIO, filename: str | None) -> IndexState:
        """Önce kontrol, sonra kayıt: standart yoksa / indeksleme sürüyorsa dosya diske hiç yazılmaz."""
        standard = self.get(standard_id)
        if standard.index_status in _BUSY:
            raise ConflictError(f"Bu standardın indekslemesi zaten sürüyor (durum: {standard.index_status}).")
        stored = self._storage.save_pdf(stream, filename)
        old_path = standard.document_path
        standard.document_path = stored.path
        standard.has_document = True
        standard.index_status = IndexStatus.PENDING
        standard.index_progress = 0.0
        standard.index_error = None
        standard.index_started_at = standard.index_finished_at = None
        self._standards.update(standard)
        if old_path:
            self._storage.delete(old_path)
        logger.info("Standart PDF'i alındı: id={} ({} KB), indeksleme kuyrukta", standard_id, stored.size_bytes // 1024)
        return standard.index_state()

    def index_document(self, standard_id: int) -> None:
        """Arka plan görevi: PDF'i indeksler. Exception dışarı sızmaz; sonuç durum alanlarına yazılır."""
        standard = self._standards.get(standard_id)
        if standard is None or standard.document_path is None:
            logger.warning("İndekslenecek standart/PDF yok: id={}", standard_id)
            return
        standard.index_status = IndexStatus.PROCESSING
        standard.index_started_at = utc_now()
        standard.index_progress = 0.1
        self._standards.update(standard)
        try:
            result = self._search.index_document(standard.id, standard.code, standard.document_path)
        except Exception:
            logger.exception("İndeksleme başarısız: id={}", standard_id)
            standard.index_status = IndexStatus.FAILED
            standard.index_error = "PDF indekslenemedi. Dosyayı kontrol edip yeniden yükleyin."
        else:
            standard.index_status = IndexStatus.INDEXED
            standard.page_count = result.page_count
            standard.chunk_count = result.chunk_count
            standard.requirement_count = result.requirement_count
            standard.index_progress = 1.0
            standard.indexed_at = utc_now()
            logger.info("İndeksleme bitti: id={} sayfa={} parça={}", standard_id, result.page_count,
                        result.chunk_count)
        standard.index_finished_at = utc_now()
        self._standards.update(standard)
