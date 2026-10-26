"""Soru → (sorgu analizi) → hibrit arama → Gemini ile kaynaklı cevap."""
from __future__ import annotations

import logging
import re
import time

from ..config import get_settings
from . import gemini
from .search import SearchOptions, hybrid_search

log = logging.getLogger(__name__)

NO_HIT = (
    "Yüklü standartlarda bu soruyla eşleşen bir madde bulamadım. Soruyu standart adı veya teknik terimle "
    "(ör. \"DO-178C yapısal kapsam\", \"MIL-STD-461G RE102\") yeniden sorabilir ya da yönetim panelinden "
    "ilgili standardın PDF'ini ekleyebilirsin."
)


def _citation(n: int, hit: dict) -> dict:
    return {
        "n": n,
        "chunk_id": hit["chunk_id"],
        "document_id": hit["document_id"],
        "code": hit["code"],
        "issuer": hit.get("issuer", ""),
        "version": hit.get("version", ""),
        "doc_title": hit["doc_title"],
        "clause_ref": hit["clause_ref"],
        "heading": hit["heading"],
        "page_start": hit["page_start"],
        "snippet": hit["snippet"],
    }


def _extractive_answer(hits: list[dict], reason: str) -> str:
    lines = [f"{reason} En ilgili maddeler:"]
    for i, h in enumerate(hits[:4], start=1):
        loc = f"{h['code']} {h['clause_ref']}".strip()
        head = f" — {h['heading']}" if h["heading"] else ""
        lines.append(f"- **{loc}**{head}: {h['snippet']} [{i}]")
    return "\n".join(lines)


def answer_question(
    question: str,
    history: list[dict],
    project: dict | None = None,
    category: str | None = None,
    boost_document_ids: list[int] | None = None,
    issuer: str | None = None,
) -> tuple[str, list[dict], dict]:
    s = get_settings()
    t0 = time.perf_counter()

    analysis = gemini.analyze_query(question, history) if s.llm_enabled else None
    standalone = analysis["standalone"] if analysis else question
    terms = analysis["terms"] if analysis else []
    codes = analysis["codes"] if analysis else []
    qvec = gemini.embed_query(standalone) if s.llm_enabled else None

    opts = SearchOptions(
        k=s.retrieval_k,
        category=category if category in ("civil", "defense") else None,
        issuer=issuer or None,
        boost_domains=(project or {}).get("domains") or [],
        boost_document_ids=boost_document_ids or [],
    )
    hits, info = hybrid_search(standalone, opts, extra_terms=terms, codes=codes, query_vec=qvec)

    meta = {
        "mode": info["mode"],
        "terms": info["tokens"][:12],
        "codes": info["codes"],
        "standalone": standalone if standalone != question else None,
        "model": None,
        "sources_scanned": len({h["document_id"] for h in hits}),
        "chunks_scanned": len(hits),
    }
    if not hits:
        meta["latency_ms"] = int((time.perf_counter() - t0) * 1000)
        return NO_HIT, [], meta

    if not s.llm_enabled:
        text = _extractive_answer(hits, "Gemini API anahtarı tanımlı olmadığı için özet cevap üretilemedi.")
        cites = [_citation(i, h) for i, h in enumerate(hits[:4], start=1)]
        meta["latency_ms"] = int((time.perf_counter() - t0) * 1000)
        return text, cites, meta

    try:
        text = gemini.generate_answer(standalone, hits, history, project)
        meta["model"] = s.gemini_model
    except Exception as e:
        log.exception("Cevap üretimi başarısız")
        text = _extractive_answer(hits, f"Model şu an cevap üretemedi ({e.__class__.__name__}).")
        cites = [_citation(i, h) for i, h in enumerate(hits[:4], start=1)]
        meta["latency_ms"] = int((time.perf_counter() - t0) * 1000)
        return text, cites, meta

    used = sorted({int(n) for n in re.findall(r"\[(\d{1,2})\]", text) if 1 <= int(n) <= len(hits)})
    if not used:
        used = list(range(1, min(3, len(hits)) + 1))
    # Geçersiz numaraları metinden temizle
    text = re.sub(r"\[(\d{1,2})\]", lambda m: m.group(0) if 1 <= int(m.group(1)) <= len(hits) else "", text)
    cites = [_citation(n, hits[n - 1]) for n in used]
    meta["latency_ms"] = int((time.perf_counter() - t0) * 1000)
    return text, cites, meta
