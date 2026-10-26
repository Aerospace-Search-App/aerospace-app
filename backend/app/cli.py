"""Komut satırı araçları.

  python -m app.cli seed [--all]          Kamuya açık standartları indir, ayrıştır, indeksle
  python -m app.cli import PATH.pdf --code "X" --title "Y" [--category defense] [--language tr] [--domains a,b]
  python -m app.cli reindex               Embedding'i eksik dokümanları tamamla (ör. API anahtarı sonradan eklendiyse)
  python -m app.cli status                Doküman durumlarını listele
"""
from __future__ import annotations

import argparse
import logging
from pathlib import Path

from . import db
from .domains import clean_domains
from .rag.ingest import DuplicateDocument, process_document, register_document
from .seed import ensure_admin, seed


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    p = argparse.ArgumentParser(prog="app.cli")
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("seed")
    s.add_argument("--all", action="store_true", help="büyük/isteğe bağlı standartları da indir (MIL-STD-810H)")
    i = sub.add_parser("import")
    i.add_argument("path")
    i.add_argument("--code", required=True)
    i.add_argument("--title", required=True)
    i.add_argument("--issuer", default="")
    i.add_argument("--category", default="civil", choices=["civil", "defense"])
    i.add_argument("--language", default="en", choices=["en", "tr"])
    i.add_argument("--domains", default="")
    sub.add_parser("reindex")
    sub.add_parser("status")
    args = p.parse_args()

    db.init_schema()
    ensure_admin()

    if args.cmd == "seed":
        res = seed(include_optional=args.all, process_inline=True)
        print(f"Eklenen: {res['added']}\nZaten vardı: {res['skipped']}\nBaşarısız: {res['failed']}")
    elif args.cmd == "import":
        meta = {"code": args.code, "title": args.title, "issuer": args.issuer, "category": args.category,
                "language": args.language, "domains": clean_domains(args.domains.split(","))}
        try:
            doc_id = register_document(Path(args.path), meta)
        except DuplicateDocument as e:
            print(f"Bu PDF zaten yüklü: #{e.document_id}")
            return
        process_document(doc_id)
        print(f"Tamamlandı: #{doc_id}")
    elif args.cmd == "reindex":
        for r in db.fetch_all("SELECT id, code FROM documents WHERE embedded_count < chunk_count OR chunk_count = 0"):
            print(f"İşleniyor: {r['code']}")
            process_document(r["id"], reparse=False)
    elif args.cmd == "status":
        for r in db.fetch_all("SELECT id, code, status, page_count, chunk_count, embedded_count, error FROM documents ORDER BY id"):
            print(f"#{r['id']:<3} {r['code']:<16} {r['status']:<13} sayfa={r['page_count']:<5} madde={r['chunk_count']:<5} "
                  f"vektör={r['embedded_count']:<5} {r['error'] or ''}")


if __name__ == "__main__":
    try:
        main()
    finally:
        db.close_pool()
