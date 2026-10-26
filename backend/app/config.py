from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(BASE_DIR.parent / ".env", BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "AeroStd Asistan API"
    database_url: str = "postgresql://aerostd:aerostd@localhost:5432/aerostd"

    # JWT
    jwt_secret: str = "change-me-in-production-please-32-chars-min"
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 60 * 24 * 7  # 7 gün
    file_token_minutes: int = 30

    # İlk admin hesabı (başlangıçta yoksa oluşturulur)
    admin_email: str = "admin@aerostd.dev"
    admin_password: str = "Admin12345!"

    # Gemini
    gemini_api_key: str = ""
    gemini_base_url: str = ""  # isteğe bağlı: vekil sunucu / test sunucusu
    gemini_model: str = "gemini-flash-latest"
    gemini_fast_model: str = "gemini-flash-lite-latest"
    embedding_model: str = "gemini-embedding-2"
    embedding_dim: int = 768
    embedding_batch_size: int = 50
    # Ücretsiz katman dakika başına token sınırına takılmamak için istekler arası bekleme (sn)
    embedding_pause_seconds: float = 1.0

    # Dosyalar
    storage_dir: Path = BASE_DIR / "data" / "standards"
    max_upload_mb: int = 150

    # RAG
    retrieval_k: int = 8
    candidate_k: int = 40
    rrf_k: int = 60

    cors_origins: str = "*"

    @property
    def llm_enabled(self) -> bool:
        return bool(self.gemini_api_key.strip())


@lru_cache
def get_settings() -> Settings:
    s = Settings()
    s.storage_dir.mkdir(parents=True, exist_ok=True)
    return s
