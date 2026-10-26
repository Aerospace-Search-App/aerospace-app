"""Kamuya açık standart PDF'lerini indirip sisteme ekler (data/standards_catalog.json)."""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path

import httpx

from . import db
from .config import BASE_DIR, get_settings
from .rag.ingest import DuplicateDocument, register_document, worker

log = logging.getLogger(__name__)
CATALOG = BASE_DIR / "data" / "standards_catalog.json"
DOWNLOAD_DIR = BASE_DIR / "data" / "downloads"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AeroStdAsistan/1.0 (academic project)"}


def load_catalog() -> list[dict]:
    return json.loads(CATALOG.read_text(encoding="utf-8"))


def _link_from_page(client: httpx.Client, page: str) -> str | None:
    html = client.get(page).text
    m = re.search(r'href="([^"]*download\.php\?spec=[^"]+\.pdf)"', html) or re.search(r'href="([^"]+\.pdf)"', html, re.I)
    return str(httpx.URL(page).join(m.group(1))) if m else None


def _fetch_pdf(client: httpx.Client, url: str, dest: Path, referer: str | None) -> bool:
    headers = {"Referer": referer} if referer else {}
    tmp = dest.with_suffix(".part")
    with client.stream("GET", url, headers=headers) as r:
        if r.status_code >= 400:
            log.warning("%s -> HTTP %s", url, r.status_code)
            return False
        with open(tmp, "wb") as f:
            for chunk in r.iter_bytes(1 << 16):
                f.write(chunk)
    with open(tmp, "rb") as f:
        ok = f.read(5) == b"%PDF-"
    if ok:
        tmp.replace(dest)
    else:
        tmp.unlink(missing_ok=True)
        log.warning("%s: PDF yerine başka içerik döndü", url)
    return ok


def download(item: dict, client: httpx.Client) -> Path | None:
    """Önce doğrudan bağlantıyı dener; olmazsa standardın sayfasından indirme bağlantısını bulur."""
    DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
    dest = DOWNLOAD_DIR / (re.sub(r"[^A-Za-z0-9._-]+", "_", item["code"]) + ".pdf")
    if dest.exists() and dest.stat().st_size > 1000:
        return dest
    page = item.get("page_url")
    candidates: list[str] = [item["url"]] if item.get("url") else []
    for attempt in range(2):
        for url in candidates:
            try:
                if _fetch_pdf(client, url, dest, page):
                    return dest
            except httpx.HTTPError as e:
                log.warning("%s: %s", url, e)
        if not page:
            break
        if attempt == 0:
            try:
                link = _link_from_page(client, page)
            except httpx.HTTPError as e:
                log.warning("%s sayfası açılamadı: %s", page, e)
                link = None
            candidates = [link] if link and link not in candidates else []
            if not candidates:
                break
    log.warning("%s indirilemedi", item["code"])
    return None


def seed(include_optional: bool = False, process_inline: bool = False) -> dict:
    """Kataloğu indirir ve kaydeder. process_inline=False ise işleme arka plan işçisine bırakılır."""
    from .rag.ingest import process_document

    result = {"added": [], "skipped": [], "failed": []}
    existing = {r["code"] for r in db.fetch_all("SELECT code FROM documents")}
    with httpx.Client(headers=UA, follow_redirects=True, timeout=180) as client:
        for item in load_catalog():
            if item.get("optional") and not include_optional:
                continue
            if item["code"] in existing:
                result["skipped"].append(item["code"])
                continue
            try:
                path = download(item, client)
                if not path:
                    result["failed"].append(item["code"])
                    continue
                meta = {**item, "source_url": item.get("url") or item.get("page_url", "")}
                doc_id = register_document(path, meta)
                result["added"].append(item["code"])
                log.info("Eklendi: %s (#%s)", item["code"], doc_id)
                if process_inline:
                    process_document(doc_id)
                else:
                    worker.enqueue(doc_id)
            except DuplicateDocument:
                result["skipped"].append(item["code"])
            except Exception as e:
                log.warning("%s indirilemedi: %s", item["code"], e)
                result["failed"].append(item["code"])
    return result


def auto_seed_if_empty() -> None:
    if db.fetch_one("SELECT 1 FROM documents LIMIT 1"):
        return
    log.info("Doküman yok — kamuya açık standartlar indiriliyor (arka planda)...")
    res = seed()
    log.info("Otomatik yükleme: %s", res)


def ensure_admin() -> None:
    from .security import hash_password

    s = get_settings()
    if not s.admin_email or not s.admin_password:
        return
    if db.fetch_one("SELECT 1 FROM users WHERE email = %s", (s.admin_email.lower(),)):
        return
    db.execute(
        """INSERT INTO users (email, username, full_name, password_hash, role)
           VALUES (%s, CASE WHEN EXISTS (SELECT 1 FROM users WHERE lower(username) = 'admin') THEN NULL ELSE 'admin' END,
                   %s, %s, 'admin')""",
        (s.admin_email.lower(), "Sistem Yöneticisi", hash_password(s.admin_password)),
    )
    log.info("Admin hesabı oluşturuldu: %s", s.admin_email)
