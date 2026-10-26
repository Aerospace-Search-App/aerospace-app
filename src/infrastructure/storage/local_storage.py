"""Yerel disk deposu: `FileStorage` arayüzünün implementasyonu (`STORAGE_DIR` klasörü).

Güvenlik kuralları (eski koddaki H4 hatası tekrarlanmasın):
- Kullanıcının dosya adı diskte **kullanılmaz**; her dosya `uuid4().hex + ".pdf"` adıyla yazılır
  (aynı adlı dosyanın üzerine yazma ve `../` ile klasör dışına çıkma imkânsız).
- Üç kontrol: uzantı `.pdf`, ilk baytlar `%PDF` (uzantıyı değiştirilmiş başka dosyalar reddedilir) ve
  `MAX_UPLOAD_MB` boyut sınırı. Dosya parça parça okunup sayılır; sınır aşılırsa yarım dosya silinir.
"""

import re
from pathlib import Path
from typing import BinaryIO
from uuid import uuid4

from src.core.errors import PayloadTooLargeError, UnsupportedFileError
from src.domain.entities import StoredFile

_PDF_SIGNATURE = b"%PDF"
_CHUNK_SIZE = 1024 * 1024  # 1 MB
_PAGE_PATTERN = re.compile(rb"/Type\s*/Page(?!s)")
_BYTES_PER_PAGE_GUESS = 50 * 1024


class LocalFileStorage:
    """PDF'leri yerel klasöre uuid adla kaydeder."""

    def __init__(self, base_dir: str, max_upload_mb: int) -> None:
        self._base_dir = Path(base_dir)
        self._max_bytes = max_upload_mb * 1024 * 1024
        self._max_upload_mb = max_upload_mb

    def save_pdf(self, stream: BinaryIO, filename: str | None) -> StoredFile:
        if not filename or not filename.lower().endswith(".pdf"):
            raise UnsupportedFileError("Sadece .pdf uzantılı dosyalar kabul edilir.")
        first = stream.read(_CHUNK_SIZE)
        if not first.startswith(_PDF_SIGNATURE):
            raise UnsupportedFileError("Dosya geçerli bir PDF değil (%PDF imzası bulunamadı).")
        self._base_dir.mkdir(parents=True, exist_ok=True)
        target = self._base_dir / f"{uuid4().hex}.pdf"
        size = 0
        try:
            with target.open("wb") as out:
                chunk = first
                while chunk:
                    size += len(chunk)
                    if size > self._max_bytes:
                        raise PayloadTooLargeError(f"Dosya boyutu {self._max_upload_mb} MB sınırını aşıyor.")
                    out.write(chunk)
                    chunk = stream.read(_CHUNK_SIZE)
        except Exception:
            target.unlink(missing_ok=True)  # yarım kalmış dosya diskte yetim kalmasın
            raise
        return StoredFile(path=str(target), size_bytes=size)

    def count_pages(self, path: str) -> int:
        """Basit tahmin: PDF içindeki `/Type /Page` nesnelerini sayar; bulamazsa boyuttan tahmin eder.

        TODO(Onur): gerçek PDF okuyucu (pypdf) ile sayfa sayısı ve metin çıkarma.
        """
        data = Path(path).read_bytes()
        pages = len(_PAGE_PATTERN.findall(data))
        return pages or max(1, len(data) // _BYTES_PER_PAGE_GUESS)

    def delete(self, path: str) -> None:
        Path(path).unlink(missing_ok=True)
