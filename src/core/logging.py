"""Loglama kurulumu (loguru).

Ne işe yarar: Uygulama genelinde tek bir log formatı ve seviyesi belirler. Kodda `print` kullanılmaz;
`from loguru import logger` ile `logger.info(...)` yazılır. Seviye `LOG_LEVEL` ayarından gelir.
"""

import sys

from loguru import logger

_LOG_FORMAT = (
    "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | "
    "<cyan>{name}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"
)


def setup_logging(level: str = "INFO") -> None:
    """Varsayılan loguru çıktısını kaldırıp seviyesi ayarlanmış tek bir konsol çıktısı ekler."""
    logger.remove()
    # diagnose=False: hata loglarında değişken değerleri (olası gizli veri) yazdırılmaz.
    logger.add(sys.stderr, level=level.upper(), format=_LOG_FORMAT, backtrace=False, diagnose=False)
