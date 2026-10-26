from __future__ import annotations

import re

import jwt
import pymupdf
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from fastapi.responses import FileResponse

from .. import db
from ..config import get_settings
from ..deps import get_current_user
from ..domains import DOMAINS
from ..rag import gemini
from ..rag.search import SearchOptions, hybrid_search
from ..schemas import ChunkOut, ClauseListItem, DocumentOut, IssuerOut, SearchHit, SearchIn, SearchOut, SourceOut
from ..security import create_file_token, decode_token
from .common import DOC_COLS, get_document, get_own_project, saved_doc_ids

router = APIRouter(prefix="/api", tags=["Standartlar ve arama"])


@router.get("/meta/domains", summary="Konu alanları (proje/standart etiketleri)")
def domains():
    return [{"key": k, **v} for k, v in DOMAINS.items()]


@router.get("/meta/issuers", response_model=list[IssuerOut], summary="Kaynak kuruluşlar (sohbet filtresi)")
def issuers(user: dict = Depends(get_current_user)):
    return db.fetch_all(
        """SELECT issuer, count(*) AS documents FROM documents
           WHERE issuer <> '' AND status <> 'failed' AND chunk_count > 0
           GROUP BY issuer ORDER BY count(*) DESC, issuer"""
    )


@router.get("/documents", response_model=list[DocumentOut], summary="Standart listesi")
def list_documents(
    q: str | None = Query(None, description="Kod veya başlıkta ara"),
    category: str | None = Query(None, pattern="^(civil|defense)$"),
    domain: str | None = None,
    user: dict = Depends(get_current_user),
):
    where, params = ["d.status <> 'failed'", "d.chunk_count > 0"], {}
    if q:
        where.append("(d.code ILIKE %(q)s OR d.title ILIKE %(q)s OR similarity(d.code, %(raw)s) > 0.3)")
        params.update(q=f"%{q.strip()}%", raw=q.strip())
    if category:
        where.append("d.category = %(category)s")
        params["category"] = category
    if domain:
        where.append("%(domain)s = ANY(d.domains)")
        params["domain"] = domain
    rows = db.fetch_all(f"SELECT {DOC_COLS} FROM documents d WHERE {' AND '.join(where)} ORDER BY d.category, d.code", params)
    saved = saved_doc_ids(user["id"])
    return [{**r, "is_saved": r["id"] in saved} for r in rows]


@router.get("/documents/{doc_id}", response_model=DocumentOut, summary="Standart detayı")
def document_detail(doc_id: int, user: dict = Depends(get_current_user)):
    doc = get_document(doc_id)
    return {**doc, "is_saved": doc_id in saved_doc_ids(user["id"])}


@router.get("/documents/{doc_id}/clauses", response_model=list[ClauseListItem], summary="Standardın madde listesi")
def document_clauses(doc_id: int, user: dict = Depends(get_current_user)):
    get_document(doc_id)
    return db.fetch_all(
        "SELECT id, ord, clause_ref, heading, page_start, part FROM chunks WHERE document_id = %s AND part = 1 ORDER BY ord",
        (doc_id,),
    )


@router.get("/chunks/{chunk_id}", response_model=SourceOut, summary="Kaynak madde (tam metin + komşular)")
def chunk_detail(chunk_id: int, user: dict = Depends(get_current_user)):
    ch = db.fetch_one(
        "SELECT id, document_id, ord, clause_ref, heading, heading_path, part, page_start, page_end, content FROM chunks WHERE id = %s",
        (chunk_id,),
    )
    if not ch:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Madde bulunamadı")
    doc = get_document(ch["document_id"])
    nb = db.fetch_one(
        """SELECT (SELECT id FROM chunks WHERE document_id = %(d)s AND ord < %(o)s ORDER BY ord DESC LIMIT 1) AS prev_id,
                  (SELECT id FROM chunks WHERE document_id = %(d)s AND ord > %(o)s ORDER BY ord LIMIT 1) AS next_id""",
        {"d": ch["document_id"], "o": ch["ord"]},
    )
    saved = db.fetch_one(
        "SELECT 1 FROM saved_items WHERE user_id = %s AND chunk_id = %s", (user["id"], chunk_id)
    )
    token = create_file_token(user["id"], doc["id"])
    return SourceOut(
        chunk=ChunkOut(**ch),
        document={**doc, "is_saved": doc["id"] in saved_doc_ids(user["id"])},
        prev_id=nb["prev_id"],
        next_id=nb["next_id"],
        is_saved=bool(saved),
        file_url=f"/api/documents/{doc['id']}/file?token={token}#page={ch['page_start']}",
        page_image_url=f"/api/documents/{doc['id']}/pages/{ch['page_start']}?token={token}&chunk={chunk_id}",
    )


def _check_file_token(token: str, doc_id: int) -> None:
    try:
        payload = decode_token(token, expected_type="file")
    except jwt.PyJWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Bağlantının süresi doldu; kaynağı yeniden açın")
    if payload.get("doc") != doc_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Bu dosyaya erişim yok")


@router.get("/documents/{doc_id}/file", summary="PDF dosyası (imzalı kısa ömürlü token ile)")
def document_file(doc_id: int, token: str):
    _check_file_token(token, doc_id)
    row = db.fetch_one("SELECT file_name, code FROM documents WHERE id = %s", (doc_id,))
    if not row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Doküman bulunamadı")
    path = get_settings().storage_dir / row["file_name"]
    if not path.exists():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "PDF dosyası sunucuda yok")
    return FileResponse(path, media_type="application/pdf", headers={"Content-Disposition": f'inline; filename="{row["file_name"]}"'})


@router.get("/documents/{doc_id}/pages/{page}", summary="Sayfa görüntüsü (PNG, madde vurgulu)")
def document_page(doc_id: int, page: int, token: str, chunk: int | None = None, zoom: float = Query(2.0, ge=1, le=3)):
    _check_file_token(token, doc_id)
    row = db.fetch_one("SELECT file_name FROM documents WHERE id = %s", (doc_id,))
    if not row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Doküman bulunamadı")
    path = get_settings().storage_dir / row["file_name"]
    with pymupdf.open(str(path)) as pdf:
        if not 1 <= page <= pdf.page_count:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Sayfa yok")
        pg = pdf[page - 1]
        if chunk:
            ch = db.fetch_one("SELECT clause_ref, heading, content FROM chunks WHERE id = %s AND document_id = %s", (chunk, doc_id))
            if ch:
                _highlight(pg, ch)
        pix = pg.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), annots=True)
        data = pix.tobytes("png")
    return Response(content=data, media_type="image/png", headers={"Cache-Control": "private, max-age=600"})


def _highlight(pg: "pymupdf.Page", ch: dict) -> None:
    """Madde başlığını ve gövdesinin ilk cümlelerini sayfada sarıyla vurgular."""
    needles = []
    if ch["clause_ref"] and ch["heading"]:
        needles.append(f"{ch['clause_ref']} {ch['heading']}"[:80])
    words = ch["content"].split()
    for i in range(0, min(len(words), 60), 8):
        frag = " ".join(words[i : i + 8])
        if len(frag) > 20:
            needles.append(re.sub(r"^…\s*", "", frag))
    rects = []
    for n in needles:
        rects.extend(pg.search_for(n, quads=False)[:2])
    if rects:
        annot = pg.add_highlight_annot(rects)
        annot.set_colors(stroke=(1.0, 0.82, 0.25))
        annot.update(opacity=0.45)


@router.post("/search", response_model=SearchOut, summary="Hibrit arama (tam metin + vektör, RRF)")
def search(body: SearchIn, user: dict = Depends(get_current_user)):
    opts = SearchOptions(k=body.k, document_ids=body.document_ids, category=body.category)
    if body.project_id:
        project = get_own_project(body.project_id, user["id"])
        opts.boost_domains = project["domains"]
    qvec = gemini.embed_query(body.query)
    hits, info = hybrid_search(body.query, opts, query_vec=qvec)
    return SearchOut(
        query=body.query,
        expanded_terms=info["tokens"],
        mode=info["mode"],
        hits=[SearchHit(**{k: h[k] for k in SearchHit.model_fields if k in h}) for h in hits],
    )
