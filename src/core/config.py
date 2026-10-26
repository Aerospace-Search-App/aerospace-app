"""Uygulama ayarları.

Ne işe yarar: Tüm ayarlar tek bir yerde, tipli olarak tutulur. Değerler sırasıyla ortam değişkenlerinden,
varsa `.env` dosyasından, yoksa aşağıdaki varsayılanlardan gelir. `.env` dosyası **opsiyoneldir**;
olmadan da uygulama mock modda ayağa kalkar. Tüm ayarlar `.env.example`'da belgelidir.

Benzetme: Bir cihazın "ayarlar menüsü" gibi; kod içinde sabit değer dağıtmak yerine herkes buraya bakar.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Ortam değişkenleri / `.env` ile ezilebilen uygulama ayarları."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    APP_NAME: str = "Aerospace Compliance Platform"
    APP_VERSION: str = "1.1.0"
    API_V1_PREFIX: str = "/api/v1"

    # false iken her istek demo kullanıcıyla çalışır. TODO(Taha): JWT bağlanınca true yapılacak.
    AUTH_ENABLED: bool = False

    # Hangi arama / LLM implementasyonunun kullanılacağı (seçim src/core/deps.py → init_app_state).
    SEARCH_PROVIDER: str = "mock"
    LLM_PROVIDER: str = "mock"
    GEMINI_API_KEY: str | None = None
    GEMINI_MODEL: str = "gemini-2.5-flash"

    # Yükleme sınırı: dosya deposu ve GET /api/v1/meta/enums aynı ayarı okur.
    # (top_k ve page_size sınırları şema sabitleridir: schemas/search.MAX_TOP_K, schemas/common.MAX_PAGE_SIZE.)
    MAX_UPLOAD_MB: int = 50

    STORAGE_DIR: str = "./storage"
    CORS_ORIGINS: list[str] = ["*"]
    LOG_LEVEL: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    """Ayarları bir kez okur ve hep aynı örneği döner (her istekte dosya okunmasın diye)."""
    return Settings()
