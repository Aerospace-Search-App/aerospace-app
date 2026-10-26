"""AeroStd Asistan — FastAPI uygulaması.

Swagger arayüzü:  http://<sunucu>:8000/docs
Yönetim paneli:   http://<sunucu>:8000/admin
"""
from __future__ import annotations

import logging
import os
import threading
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from . import db
from .config import get_settings
from .rag.ingest import worker
from .routers import admin, auth, chat, documents, projects, saved
from .seed import auto_seed_if_empty, ensure_admin

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("aerostd")


@asynccontextmanager
async def lifespan(app: FastAPI):
    s = get_settings()
    db.init_schema()
    db.open_pool()
    ensure_admin()
    worker.start()
    worker.resume_unfinished()
    if os.getenv("AUTO_SEED", "true").lower() == "true":
        threading.Thread(target=auto_seed_if_empty, name="auto-seed", daemon=True).start()
    log.info("Hazır. Gemini: %s", "AÇIK" if s.llm_enabled else "KAPALI (yalnızca tam metin arama)")
    yield
    db.close_pool()


app = FastAPI(
    title="AeroStd Asistan API",
    version="1.0.0",
    description=(
        "Sivil havacılık ve savunma standartları için RAG tabanlı asistan.\n\n"
        "**Kullanım:** `/api/auth/register` veya `/api/auth/login` ile token alın, sağ üstteki **Authorize** "
        "düğmesine yapıştırın.\n\n"
        "**RAG hattı:** PDF → madde bazlı parçalama → PostgreSQL (tsvector + pgvector) → hibrit arama (RRF) → "
        "Gemini ile kaynaklı cevap."
    ),
    lifespan=lifespan,
    swagger_ui_parameters={"persistAuthorization": True, "docExpansion": "none"},
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in get_settings().cors_origins.split(",")],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(RequestValidationError)
async def validation_handler(request: Request, exc: RequestValidationError):
    msgs = []
    for e in exc.errors():
        field = ".".join(str(x) for x in e.get("loc", [])[1:]) or "istek"
        msg = e.get("msg", "Geçersiz değer").replace("Value error, ", "")
        msgs.append(f"{field}: {msg}")
    return JSONResponse(status_code=422, content={"detail": "; ".join(msgs)})


for r in (auth.router, documents.router, chat.router, projects.router, saved.router, admin.router):
    app.include_router(r)


@app.get("/api/health", tags=["Sistem"], summary="Sağlık kontrolü")
def health():
    s = get_settings()
    row = db.fetch_one("SELECT count(*) AS docs FROM documents WHERE chunk_count > 0")
    return {"status": "ok", "llm_enabled": s.llm_enabled, "documents": row["docs"]}


@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse("/docs")


app.mount("/admin", StaticFiles(directory=Path(__file__).parent / "static" / "admin", html=True), name="admin")
