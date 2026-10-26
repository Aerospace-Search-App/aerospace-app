"""Ortak test altyapısı.

- Her test kendi temiz uygulamasını `create_app()` ile alır (`with TestClient(app)` -> lifespan çalışır).
- Ayarlar ortam değişkenleriyle sabitlenir (olası bir yerel `.env` testleri etkilemesin diye) ve
  `STORAGE_DIR` testin `tmp_path`'ine yönlendirilir. `get_settings` önbelleği her testte temizlenir.
"""

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.core.config import get_settings

_TEST_ENV = {
    "APP_NAME": "Aerospace Compliance Platform",
    "APP_VERSION": "1.1.0",
    "API_V1_PREFIX": "/api/v1",
    "AUTH_ENABLED": "false",
    "SEARCH_PROVIDER": "mock",
    "LLM_PROVIDER": "mock",
    "MAX_UPLOAD_MB": "50",
    "LOG_LEVEL": "WARNING",
}


@pytest.fixture(autouse=True)
def _isolated_settings(monkeypatch: pytest.MonkeyPatch, tmp_path) -> Iterator[None]:
    for key, value in _TEST_ENV.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setenv("STORAGE_DIR", str(tmp_path / "storage"))
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def app() -> FastAPI:
    """Her test için sıfırdan kurulmuş uygulama."""
    from main import create_app

    return create_app()


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    """Lifespan'i çalıştıran TestClient (sunucu hataları test içinde exception olarak yükselir)."""
    with TestClient(app) as c:
        yield c


@pytest.fixture
def client_no_raise(app: FastAPI) -> Iterator[TestClient]:
    """500 testleri için: beklenmeyen hatalar exception yerine 500 cevabı olarak döner."""
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


@pytest.fixture
def pdf_bytes() -> bytes:
    """`%PDF` ile başlayan küçük sahte PDF (Faz 3+ yükleme testleri için)."""
    return (
        b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
        b"2 0 obj\n<< /Type /Pages /Kids [] /Count 0 >>\nendobj\ntrailer\n<< /Root 1 0 R >>\n%%EOF\n"
    )


@pytest.fixture
def fake_pdf() -> tuple[str, bytes, str]:
    """`.pdf` uzantılı ama `%PDF` ile başlamayan dosya (beklenen: 415 UNSUPPORTED_FILE)."""
    return ("sahte.pdf", b"Bu bir PDF degil, duz metin.\n", "application/pdf")


@pytest.fixture
def storage_dir(tmp_path) -> Path:
    """Testin dosya deposu klasörü (`STORAGE_DIR`); dosya yazılmadıysa hiç oluşmamış olabilir."""
    return tmp_path / "storage"


@pytest.fixture
def make_client(monkeypatch: pytest.MonkeyPatch):
    """Farklı ayarlarla (ör. `LLM_PROVIDER=gemini`, `AUTH_ENABLED=true`) temiz uygulama + TestClient üretir.

        c = make_client(LLM_PROVIDER="gemini")
    """
    from contextlib import ExitStack

    stack = ExitStack()

    def _make(**env: str) -> TestClient:
        for key, value in env.items():
            monkeypatch.setenv(key, value)
        get_settings.cache_clear()
        from main import create_app

        return stack.enter_context(TestClient(create_app()))

    with stack:
        yield _make
