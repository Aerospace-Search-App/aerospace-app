"""Doküman kaydı, madde bazlı parçaların veritabanına yüklenmesi ve arka planda embedding.

Akış:  queued → parsing → (chunks yazılır, tam metin arama hemen çalışır)
       → embedding (Gemini, oran sınırına uygun partiler) → ready
       Gemini anahtarı yoksa: lexical_only (anahtar eklenince otomatik tamamlanır)
"""
from __future__ import annotations

import hashlib
import logging
import queue
import re
import shutil
import threading
import time
from pathlib import Path

from .. import db
from ..config import get_settings
from . import gemini
from .parser import parse_pdf

log = logging.getLogger(__name__)

TS_CONFIG = {"en": "english", "tr": "turkish"}

INSERT_CHUNK = """
INSERT INTO chunks (document_id, ord, clause_ref, heading, heading_path, part, page_start, page_end,
                    content, token_count, tsv)
VALUES (%(document_id)s, %(ord)s, %(clause_ref)s, %(heading)s, %(heading_path)s, %(part)s, %(page_start)s,
        %(page_end)s, %(content)s, %(token_count)s,
        setweight(to_tsvector('simple', %(codes)s), 'A')
        || setweight(to_tsvector(%(cfg)s::regconfig, %(heading_path)s), 'A')
        || setweight(to_tsvector(%(cfg)s::regconfig, %(content)s), 'B')
        || setweight(to_tsvector('simple', %(content)s), 'D'))
"""


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def safe_name(code: str, original: str) -> str:
    base = re.sub(r"[^A-Za-z0-9._-]+", "_", code or Path(original).stem).strip("_") or "document"
    return f"{base}.pdf"


class DuplicateDocument(Exception):
    def __init__(self, document_id: int):
        self.document_id = document_id


def register_document(src: Path, meta: dict, uploaded_by: int | None = None, move: bool = False) -> int:
    """PDF'i depolama klasörüne alır ve documents tablosuna 'queued' olarak ekler."""
    s = get_settings()
    digest = sha256_file(src)
    existing = db.fetch_one("SELECT id FROM documents WHERE file_sha256 = %s", (digest,))
    if existing:
        raise DuplicateDocument(existing["id"])

    name = safe_name(meta.get("code", ""), src.name)
    dest = s.storage_dir / name
    if dest.exists() and dest.resolve() != src.resolve():
        dest = s.storage_dir / f"{dest.stem}_{digest[:8]}.pdf"
    if dest.resolve() != src.resolve():
        (shutil.move if move else shutil.copyfile)(str(src), str(dest))

    row = db.fetch_one(
        """INSERT INTO documents (code, title, issuer, category, domains, language, version, published_on,
                                  summary, source_url, file_name, file_sha256, uploaded_by)
           VALUES (%(code)s, %(title)s, %(issuer)s, %(category)s, %(domains)s, %(language)s, %(version)s,
                   %(published_on)s, %(summary)s, %(source_url)s, %(file_name)s, %(sha)s, %(uploaded_by)s)
           RETURNING id""",
        {
            "code": meta.get("code") or Path(src.name).stem,
            "title": meta.get("title") or meta.get("code") or src.stem,
            "issuer": meta.get("issuer", ""),
            "category": meta.get("category", "civil"),
            "domains": meta.get("domains", []),
            "language": meta.get("language", "en"),
            "version": meta.get("version", ""),
            "published_on": meta.get("published_on", ""),
            "summary": meta.get("summary", ""),
            "source_url": meta.get("source_url", ""),
            "file_name": dest.name,
            "sha": digest,
            "uploaded_by": uploaded_by,
        },
    )
    return row["id"]


def _set_status(doc_id: int, status: str, **fields) -> None:
    sets = ", ".join(f"{k} = %({k})s" for k in fields)
    db.execute(
        f"UPDATE documents SET status = %(status)s, updated_at = now(){', ' + sets if sets else ''} WHERE id = %(id)s",
        {"status": status, "id": doc_id, **fields},
    )


def parse_and_store(doc_id: int) -> int:
    s = get_settings()
    doc = db.fetch_one("SELECT * FROM documents WHERE id = %s", (doc_id,))
    if not doc:
        return 0
    _set_status(doc_id, "parsing", error=None)
    parsed = parse_pdf(s.storage_dir / doc["file_name"])
    cfg = TS_CONFIG.get(doc["language"], "english")
    rows = [
        {
            "document_id": doc_id,
            "ord": c.ord,
            "clause_ref": c.clause_ref,
            "heading": c.heading,
            "heading_path": c.heading_path,
            "part": c.part,
            "page_start": c.page_start,
            "page_end": c.page_end,
            "content": c.content,
            "token_count": int(c.word_count * 1.35),
            "codes": f"{doc['code']} {doc['code'].replace('-', '')} {c.clause_ref}",
            "cfg": cfg,
        }
        for c in parsed.chunks
    ]
    with db.get_conn() as conn:
        with conn.transaction():
            conn.execute("DELETE FROM chunks WHERE document_id = %s", (doc_id,))
            with conn.cursor() as cur:
                cur.executemany(INSERT_CHUNK, rows)
            conn.execute(
                "UPDATE documents SET page_count = %s, chunk_count = %s, embedded_count = 0, updated_at = now() WHERE id = %s",
                (parsed.page_count, len(rows), doc_id),
            )
    log.info("%s: %d sayfa, %d madde parçası (yapılı=%s)", doc["code"], parsed.page_count, len(rows), parsed.structured)
    return len(rows)


def maybe_summarize(doc_id: int) -> None:
    doc = db.fetch_one("SELECT code, title, summary FROM documents WHERE id = %s", (doc_id,))
    if not doc or doc["summary"]:
        return
    first = db.fetch_all("SELECT content FROM chunks WHERE document_id = %s ORDER BY ord LIMIT 4", (doc_id,))
    text = "\n".join(r["content"] for r in first)[:5000]
    summary = ""
    if get_settings().llm_enabled:
        try:
            summary = gemini._generate(
                get_settings().gemini_fast_model,
                f"Standart: {doc['code']} — {doc['title']}\n\nİlk bölümler:\n{text}\n\n"
                "Bu standardın neyi kapsadığını ve kimin kullanması gerektiğini 2 cümlelik Türkçe özetle.",
                "Havacılık standartlarını kısa ve doğru özetlersin.",
                max_tokens=200,
            )
        except Exception as e:
            log.warning("Özet üretilemedi: %s", e)
    if not summary:
        summary = " ".join(text.split()[:45]) + ("…" if len(text.split()) > 45 else "")
    db.execute("UPDATE documents SET summary = %s WHERE id = %s", (summary[:800], doc_id))


def embed_pending(doc_id: int) -> None:
    s = get_settings()
    doc = db.fetch_one("SELECT code FROM documents WHERE id = %s", (doc_id,))
    while True:
        batch = db.fetch_all(
            """SELECT id, clause_ref, heading, heading_path, content FROM chunks
               WHERE document_id = %s AND embedding IS NULL ORDER BY ord LIMIT %s""",
            (doc_id, s.embedding_batch_size),
        )
        if not batch:
            break
        items = [
            (f"{doc['code']} {r['clause_ref']} {r['heading']}".strip(), f"{r['heading_path']}\n{r['content']}"[:7000])
            for r in batch
        ]
        vectors = gemini.embed_documents(items)
        with db.get_conn() as conn:
            with conn.cursor() as cur:
                cur.executemany(
                    "UPDATE chunks SET embedding = %s::vector WHERE id = %s",
                    [(str(v), r["id"]) for v, r in zip(vectors, batch)],
                )
            conn.execute(
                "UPDATE documents SET embedded_count = (SELECT count(*) FROM chunks WHERE document_id = %s AND embedding IS NOT NULL), updated_at = now() WHERE id = %s",
                (doc_id, doc_id),
            )
        time.sleep(s.embedding_pause_seconds)


def process_document(doc_id: int, reparse: bool = True) -> None:
    try:
        doc = db.fetch_one("SELECT id, chunk_count FROM documents WHERE id = %s", (doc_id,))
        if not doc:
            return
        if reparse or doc["chunk_count"] == 0:
            parse_and_store(doc_id)
        maybe_summarize(doc_id)
        if not get_settings().llm_enabled:
            _set_status(doc_id, "lexical_only")
            return
        _set_status(doc_id, "embedding")
        embed_pending(doc_id)
        _set_status(doc_id, "ready", error=None)
    except Exception as e:  # doküman bazında hata, worker çalışmaya devam eder
        log.exception("Doküman %s işlenemedi", doc_id)
        status = "lexical_only" if _has_chunks(doc_id) else "failed"
        _set_status(doc_id, status, error=str(e)[:500])


def _has_chunks(doc_id: int) -> bool:
    r = db.fetch_one("SELECT count(*) AS n FROM chunks WHERE document_id = %s", (doc_id,))
    return bool(r and r["n"])


# ---------------------------------------------------------------------------
# Arka plan işçisi: dokümanları sırayla işler (oran sınırlarını aşmamak için tek iş parçacığı)
# ---------------------------------------------------------------------------
class IngestWorker:
    def __init__(self) -> None:
        self.q: queue.Queue[tuple[int, bool]] = queue.Queue()
        self._pending: set[int] = set()
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self._run, name="ingest-worker", daemon=True)
        self._thread.start()

    def enqueue(self, doc_id: int, reparse: bool = True) -> None:
        with self._lock:
            if doc_id in self._pending:
                return
            self._pending.add(doc_id)
        self.q.put((doc_id, reparse))

    def resume_unfinished(self) -> None:
        rows = db.fetch_all(
            """SELECT id, chunk_count, status FROM documents
               WHERE status IN ('queued', 'parsing', 'embedding')
                  OR (status = 'lexical_only' AND %s AND embedded_count < chunk_count)
               ORDER BY id""",
            (get_settings().llm_enabled,),
        )
        for r in rows:
            self.enqueue(r["id"], reparse=r["chunk_count"] == 0 or r["status"] in ("queued", "parsing"))

    def _run(self) -> None:
        while True:
            doc_id, reparse = self.q.get()
            try:
                process_document(doc_id, reparse)
            finally:
                with self._lock:
                    self._pending.discard(doc_id)
                self.q.task_done()

    def is_busy(self) -> bool:
        return bool(self._pending)


worker = IngestWorker()
