"""Hibrit arama: PostgreSQL tam metin (tsvector, BM25 benzeri ts_rank_cd) + pgvector (kosinüs)
sonuçları Reciprocal Rank Fusion (RRF) ile birleştirilir.

Neden hibrit?  Standartlarda kesin kodlar ("RE102", "145.A.30", "MC/DC", "Level A") lexical aramada,
anlam benzerliği ("yazılım doğrulama kapsamı" ↔ "structural coverage analysis") vektör aramada güçlüdür.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from .. import db
from ..config import get_settings

STOP = {
    # en
    "the", "a", "an", "of", "to", "in", "for", "and", "or", "is", "are", "be", "on", "by", "with", "what", "which",
    "how", "when", "does", "do", "should", "shall", "must", "can", "this", "that", "it", "as", "at", "from", "i", "we",
    "my", "our", "about", "need", "required", "requirements",
    # tr
    "ve", "ile", "bir", "bu", "şu", "için", "ne", "nedir", "nasıl", "hangi", "mi", "mı", "mu", "mü", "de", "da",
    "ki", "gibi", "olarak", "olan", "veya", "ya", "daha", "en", "çok", "var", "yok", "gerekir", "gerekiyor",
    "gereken", "neler", "nelerdir", "kadar", "göre", "ilgili", "hakkında", "benim", "bana", "projemde", "projem",
}
WORD_RE = re.compile(r"[0-9A-Za-zÇĞİÖŞÜçğıöşü]+")
CODE_RE = re.compile(
    r"\b((?:MIL|DOD)-(?:STD|HDBK|PRF|DTL)-\d+[A-Z]?|DO-\d{3}[A-Z]?|ED-\d{2,3}[A-Z]?|ARP\s?\d{4}[A-Z]?|AC\s?\d{2,3}[-.]\d+[A-Z\-\d.]*|"
    r"SH[TY]-[\w.]+|CS-\d+|Part[- ]\d+|AS\d{4}[A-Z]?|NASA-STD-[\d.]+[A-Z]?)\b",
    re.I,
)


@dataclass
class SearchOptions:
    k: int = 8
    document_ids: list[int] | None = None
    category: str | None = None             # civil / defense
    issuer: str | None = None               # FAA, SHGM, DoD ...
    boost_domains: list[str] = field(default_factory=list)
    boost_document_ids: list[int] = field(default_factory=list)
    candidate_k: int | None = None


def tokens_for(query: str, extra_terms: list[str] | None = None) -> list[str]:
    seen: list[str] = []
    for src in [query, *(extra_terms or [])]:
        for w in WORD_RE.findall(src):
            lw = w.replace("İ", "i").replace("I", "ı" if not w.isascii() else "I").lower()
            if lw in STOP or (len(lw) < 2 and not lw.isdigit()):
                continue
            if lw not in seen:
                seen.append(lw)
    return seen[:40]


def detect_codes(text: str) -> list[str]:
    return list(dict.fromkeys(m.group(1).upper().replace(" ", "") for m in CODE_RE.finditer(text)))


def _filters(opts: SearchOptions, params: dict) -> str:
    where = ["d.status <> 'failed'"]
    if opts.document_ids:
        where.append("d.id = ANY(%(doc_ids)s)")
        params["doc_ids"] = opts.document_ids
    if opts.category in ("civil", "defense"):
        where.append("d.category = %(category)s")
        params["category"] = opts.category
    if opts.issuer:
        where.append("lower(d.issuer) = lower(%(issuer)s)")
        params["issuer"] = opts.issuer
    return " AND ".join(where)


def lexical_search(tokens: list[str], opts: SearchOptions, limit: int) -> list[int]:
    if not tokens:
        return []
    params: dict = {"q": " | ".join(tokens), "limit": limit}
    sql = f"""
        WITH q AS (
            SELECT to_tsquery('english', %(q)s) || to_tsquery('turkish', %(q)s) || to_tsquery('simple', %(q)s) AS query
        )
        SELECT c.id
        FROM chunks c JOIN documents d ON d.id = c.document_id, q
        WHERE c.tsv @@ q.query AND {_filters(opts, params)}
        ORDER BY ts_rank_cd(c.tsv, q.query, 32) DESC, c.id
        LIMIT %(limit)s
    """
    return [r["id"] for r in db.fetch_all(sql, params)]


def vector_search(vec: list[float] | None, opts: SearchOptions, limit: int) -> list[int]:
    if vec is None:
        return []
    params: dict = {"v": str(vec), "limit": limit}
    sql = f"""
        SELECT c.id
        FROM chunks c JOIN documents d ON d.id = c.document_id
        WHERE c.embedding IS NOT NULL AND {_filters(opts, params)}
        ORDER BY c.embedding <=> %(v)s::vector
        LIMIT %(limit)s
    """
    with db.get_conn() as conn:
        conn.execute("SET LOCAL hnsw.ef_search = 100")
        return [r["id"] for r in conn.execute(sql, params).fetchall()]


def _snippet(content: str, tokens: list[str], size: int = 260) -> str:
    text = " ".join(content.split())
    low = text.lower()
    pos = min((low.find(t) for t in tokens if len(t) > 3 and low.find(t) >= 0), default=0)
    start = max(0, pos - 60)
    if start > 0:
        sp = text.find(" ", start)
        start = sp + 1 if 0 <= sp < pos else start
    out = text[start : start + size]
    return ("…" if start > 0 else "") + out + ("…" if start + size < len(text) else "")


def hybrid_search(
    query: str,
    opts: SearchOptions,
    *,
    extra_terms: list[str] | None = None,
    codes: list[str] | None = None,
    query_vec: list[float] | None = None,
) -> tuple[list[dict], dict]:
    s = get_settings()
    cand = opts.candidate_k or s.candidate_k
    tokens = tokens_for(query, extra_terms)
    codes = list(dict.fromkeys([*(codes or []), *detect_codes(query)]))

    lex = lexical_search(tokens, opts, cand)
    vec = vector_search(query_vec, opts, cand)

    scores: dict[int, float] = {}
    lex_rank = {cid: i + 1 for i, cid in enumerate(lex)}
    vec_rank = {cid: i + 1 for i, cid in enumerate(vec)}
    for cid, r in lex_rank.items():
        scores[cid] = scores.get(cid, 0) + 1 / (s.rrf_k + r)
    for cid, r in vec_rank.items():
        scores[cid] = scores.get(cid, 0) + 1 / (s.rrf_k + r)
    if not scores:
        return [], {"tokens": tokens, "codes": codes, "mode": "hybrid" if query_vec else "lexical"}

    rows = db.fetch_all(
        """SELECT c.id AS chunk_id, c.document_id, c.clause_ref, c.heading, c.heading_path, c.page_start, c.page_end,
                  c.content, d.code, d.title AS doc_title, d.domains, d.category, d.issuer, d.version
           FROM chunks c JOIN documents d ON d.id = c.document_id WHERE c.id = ANY(%s)""",
        (list(scores),),
    )
    norm_codes = [c.replace("-", "").replace(" ", "").upper() for c in codes]
    for r in rows:
        sc = scores[r["chunk_id"]]
        doc_code = r["code"].replace("-", "").replace(" ", "").upper()
        if norm_codes and any(nc in doc_code or doc_code in nc for nc in norm_codes if len(nc) >= 4):
            sc += 0.02  # soruda adı geçen standarda öncelik
        clause_norm = r["clause_ref"].replace(" ", "").upper()
        if clause_norm and any(clause_norm == nc for nc in norm_codes):
            sc += 0.02
        if not r["clause_ref"] and r["heading"] == "Ön bölüm":
            sc *= 0.6  # kapak / ön söz sayfaları asıl maddelerin önüne geçmesin
        if opts.boost_domains and set(r["domains"]) & set(opts.boost_domains):
            sc *= 1.15
        if r["document_id"] in opts.boost_document_ids:
            sc *= 1.1
        r["score"] = round(sc, 5)
        r["lexical_rank"] = lex_rank.get(r["chunk_id"])
        r["vector_rank"] = vec_rank.get(r["chunk_id"])
        r["snippet"] = _snippet(r["content"], tokens)
    rows.sort(key=lambda r: r["score"], reverse=True)
    return rows[: opts.k], {"tokens": tokens, "codes": codes, "mode": "hybrid" if vec else "lexical"}
