from __future__ import annotations

from fastapi import APIRouter, Depends, status

from .. import db
from ..deps import get_current_user
from ..domains import DOMAINS, clean_domains
from ..rag import gemini
from ..rag.search import SearchOptions, hybrid_search
from ..schemas import ProjectIn, ProjectOut, Recommendation
from .common import DOC_COLS, get_own_project, saved_doc_ids

router = APIRouter(prefix="/api/projects", tags=["Projeler"])

LIST_SQL = """
SELECT p.*, (SELECT count(*) FROM saved_items s WHERE s.project_id = p.id) AS saved_count,
       (SELECT count(*) FROM conversations c WHERE c.project_id = p.id) AS conversation_count
FROM projects p WHERE p.user_id = %(u)s {extra} ORDER BY p.updated_at DESC
"""


@router.get("", response_model=list[ProjectOut], summary="Projelerim")
def list_projects(user: dict = Depends(get_current_user)):
    return db.fetch_all(LIST_SQL.format(extra=""), {"u": user["id"]})


@router.post("", response_model=ProjectOut, status_code=status.HTTP_201_CREATED, summary="Proje oluştur")
def create_project(body: ProjectIn, user: dict = Depends(get_current_user)):
    row = db.fetch_one(
        "INSERT INTO projects (user_id, name, description, category, domains) VALUES (%s, %s, %s, %s, %s) RETURNING id",
        (user["id"], body.name.strip(), body.description.strip(), body.category, clean_domains(body.domains)),
    )
    return db.fetch_one(LIST_SQL.format(extra="AND p.id = %(p)s"), {"u": user["id"], "p": row["id"]})


@router.get("/{project_id}", response_model=ProjectOut, summary="Proje detayı")
def get_project(project_id: int, user: dict = Depends(get_current_user)):
    get_own_project(project_id, user["id"])
    return db.fetch_one(LIST_SQL.format(extra="AND p.id = %(p)s"), {"u": user["id"], "p": project_id})


@router.put("/{project_id}", response_model=ProjectOut, summary="Projeyi güncelle")
def update_project(project_id: int, body: ProjectIn, user: dict = Depends(get_current_user)):
    get_own_project(project_id, user["id"])
    db.execute(
        "UPDATE projects SET name=%s, description=%s, category=%s, domains=%s, updated_at=now() WHERE id=%s",
        (body.name.strip(), body.description.strip(), body.category, clean_domains(body.domains), project_id),
    )
    return get_project(project_id, user)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Projeyi sil")
def delete_project(project_id: int, user: dict = Depends(get_current_user)):
    get_own_project(project_id, user["id"])
    db.execute("DELETE FROM projects WHERE id = %s", (project_id,))


@router.get("/{project_id}/recommendations", response_model=list[Recommendation],
            summary="Projeye göre bilinmesi gereken standartlar")
def recommendations(project_id: int, user: dict = Depends(get_current_user)):
    """Proje açıklaması ile hibrit arama yapılır, sonuçlar doküman bazında toplanır;
    projenin konu alanlarıyla eşleşen standartlar ek puan alır."""
    project = get_own_project(project_id, user["id"])
    hints = " ".join(f"{DOMAINS[d]['label']} {DOMAINS[d]['hint']}" for d in project["domains"] if d in DOMAINS)
    query = f"{project['name']}. {project['description']} {hints}".strip()
    category = project["category"] if project["category"] in ("civil", "defense") else None

    hits, _ = hybrid_search(
        query,
        SearchOptions(k=60, category=category, boost_domains=project["domains"], candidate_k=80),
        query_vec=gemini.embed_query(query),
    )
    by_doc: dict[int, dict] = {}
    for h in hits:
        d = by_doc.setdefault(h["document_id"], {"score": 0.0, "clauses": [], "n": 0})
        d["n"] += 1
        if len(d["clauses"]) < 3:
            d["score"] += h["score"]
            d["clauses"].append({k: h[k] for k in ("chunk_id", "clause_ref", "heading", "page_start", "snippet")})

    where = ["d.status <> 'failed'", "d.chunk_count > 0"]
    params: dict = {"ids": list(by_doc), "domains": project["domains"]}
    if category:
        where.append("d.category = %(cat)s")
        params["cat"] = category
    docs = db.fetch_all(
        f"""SELECT {DOC_COLS} FROM documents d
            WHERE {' AND '.join(where)} AND (d.id = ANY(%(ids)s) OR d.domains && %(domains)s::text[])""",
        params,
    )
    saved = saved_doc_ids(user["id"])
    out = []
    for doc in docs:
        agg = by_doc.get(doc["id"], {"score": 0.0, "clauses": [], "n": 0})
        overlap = [d for d in doc["domains"] if d in project["domains"]]
        score = agg["score"] + 0.03 * len(overlap)
        reasons = []
        if overlap:
            reasons.append("Alan eşleşmesi: " + ", ".join(DOMAINS[d]["label"] for d in overlap))
        if agg["n"]:
            reasons.append(f"Proje tanımınla ilgili {agg['n']} madde")
        out.append({"document": {**doc, "is_saved": doc["id"] in saved}, "score": round(score, 4),
                    "reasons": reasons, "clauses": agg["clauses"]})
    out.sort(key=lambda r: r["score"], reverse=True)
    return out[:10]
