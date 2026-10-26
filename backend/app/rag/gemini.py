"""Google Gemini istemcisi: embedding, sorgu analizi ve kaynaklı cevap üretimi.

Anahtar tanımlı değilse tüm fonksiyonlar sessizce devre dışı kalır; sistem yalnızca
tam metin (lexical) arama ve alıntı tabanlı cevap ile çalışmaya devam eder.
"""
from __future__ import annotations

import json
import logging
import math
import re
import threading
import time
from typing import Any

from ..config import get_settings

log = logging.getLogger(__name__)
_client = None
_lock = threading.Lock()


class GeminiUnavailable(RuntimeError):
    pass


def client():
    global _client
    s = get_settings()
    if not s.llm_enabled:
        raise GeminiUnavailable("GEMINI_API_KEY tanımlı değil")
    with _lock:
        if _client is None:
            from google import genai
            from google.genai import types

            opts = types.HttpOptions(base_url=s.gemini_base_url) if s.gemini_base_url else None
            _client = genai.Client(api_key=s.gemini_api_key.strip(), http_options=opts)
    return _client


def _retry(fn, what: str, attempts: int = 6):
    from google.genai import errors

    delay = 4.0
    for i in range(attempts):
        try:
            return fn()
        except errors.APIError as e:
            code = getattr(e, "code", 0) or 0
            if code in (429, 500, 502, 503, 504) and i < attempts - 1:
                m = re.search(r"retry in ([\d\.]+)s", str(e), re.I) or re.search(r"retryDelay.{0,5}?(\d+)s", str(e))
                wait = float(m.group(1)) + 1 if m else delay
                log.warning("%s: Gemini %s, %.0f sn sonra tekrar denenecek", what, code, wait)
                time.sleep(min(wait, 70))
                delay = min(delay * 2, 60)
                continue
            raise


# ---------------------------------------------------------------------------
# Embedding
# ---------------------------------------------------------------------------
def _normalize(v: list[float]) -> list[float]:
    n = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / n for x in v]


def _uses_task_type(model: str) -> bool:
    return "embedding-001" in model or "text-embedding" in model


def embed_documents(items: list[tuple[str, str]]) -> list[list[float]]:
    """items: (başlık, metin) çiftleri. Döküman tarafı embedding'leri."""
    from google.genai import types

    s = get_settings()
    if _uses_task_type(s.embedding_model):
        contents = [f"{t}\n{x}" for t, x in items]
        cfg = types.EmbedContentConfig(task_type="RETRIEVAL_DOCUMENT", output_dimensionality=s.embedding_dim)
    else:  # gemini-embedding-2: görev talimatı metnin içinde verilir
        contents = [f"title: {t or 'none'} | text: {x}" for t, x in items]
        cfg = types.EmbedContentConfig(output_dimensionality=s.embedding_dim)
    # Her metin ayrı Content olmalı; düz liste verilirse SDK hepsini tek içerikte birleştirir (tek vektör döner)
    payload = [types.Content(role="user", parts=[types.Part(text=c)]) for c in contents]
    res = _retry(lambda: client().models.embed_content(model=s.embedding_model, contents=payload, config=cfg), "embed")
    if len(res.embeddings) != len(items):
        raise RuntimeError(f"Embedding sayısı uyuşmuyor: {len(res.embeddings)} != {len(items)}")
    return [_normalize(list(e.values)) for e in res.embeddings]


def embed_query(text: str) -> list[float] | None:
    from google.genai import types

    s = get_settings()
    if not s.llm_enabled:
        return None
    try:
        if _uses_task_type(s.embedding_model):
            cfg = types.EmbedContentConfig(task_type="RETRIEVAL_QUERY", output_dimensionality=s.embedding_dim)
            content = text
        else:
            cfg = types.EmbedContentConfig(output_dimensionality=s.embedding_dim)
            content = f"task: search result | query: {text}"
        payload = [types.Content(role="user", parts=[types.Part(text=content)])]
        res = _retry(lambda: client().models.embed_content(model=s.embedding_model, contents=payload, config=cfg), "embed_query", 3)
        return _normalize(list(res.embeddings[0].values))
    except Exception as e:  # arama vektörsüz devam edebilir
        log.warning("Sorgu embedding'i alınamadı: %s", e)
        return None


# ---------------------------------------------------------------------------
# Metin üretimi
# ---------------------------------------------------------------------------
def _generate(model: str, prompt: Any, system: str, *, json_mode: bool = False, temperature: float = 0.2, max_tokens: int = 2048) -> str:
    from google.genai import types

    base = dict(system_instruction=system, temperature=temperature, max_output_tokens=max_tokens)
    if json_mode:
        base["response_mime_type"] = "application/json"

    def call(cfg):
        return client().models.generate_content(model=model, contents=prompt, config=cfg)

    try:  # düşük düşünme seviyesi = hızlı yanıt; desteklemeyen modelde yapılandırmasız tekrar dene
        res = _retry(lambda: call(types.GenerateContentConfig(**base, thinking_config=types.ThinkingConfig(thinking_level="low"))), "generate", 3)
    except Exception as e:
        if "thinking" not in str(e).lower():
            raise
        res = _retry(lambda: call(types.GenerateContentConfig(**base)), "generate", 3)
    return (res.text or "").strip()


QUERY_SYSTEM = """Havacılık ve savunma standartları arama motoru için sorgu analizcisisin.
Kullanıcının son sorusunu (gerekirse önceki konuşmaya göre) tek başına anlaşılır hale getir ve
tam metin arama için anahtar terimler üret. Standart dokümanlar çoğunlukla İngilizcedir, bazıları Türkçedir.
Yalnızca şu JSON'u döndür:
{"standalone": "...", "terms_en": ["..."], "terms_tr": ["..."], "codes": ["..."]}
- terms_en: 3-8 İngilizce teknik terim/eşanlamlı (ör. "software level A", "structural coverage", "MC/DC")
- terms_tr: 2-5 Türkçe terim
- codes: soruda geçen standart/madde kodları (ör. "DO-178C", "MIL-STD-461G", "RE102", "145.A.30"); yoksa []"""


def analyze_query(question: str, history: list[dict]) -> dict | None:
    s = get_settings()
    if not s.llm_enabled:
        return None
    hist = "\n".join(f"{m['role']}: {m['content'][:400]}" for m in history[-4:])
    prompt = f"Önceki konuşma:\n{hist or '(yok)'}\n\nSon soru: {question}"
    try:
        raw = _generate(s.gemini_fast_model, prompt, QUERY_SYSTEM, json_mode=True, temperature=0.0, max_tokens=400)
        data = json.loads(re.sub(r"^```(json)?|```$", "", raw.strip()).strip())
        return {
            "standalone": str(data.get("standalone") or question)[:1000],
            "terms": [str(t) for t in (data.get("terms_en") or []) + (data.get("terms_tr") or [])][:14],
            "codes": [str(c) for c in (data.get("codes") or [])][:6],
        }
    except Exception as e:
        log.warning("Sorgu analizi başarısız: %s", e)
        return None


ANSWER_SYSTEM = """Sen "AeroStandart AI"sın: sivil havacılık ve savunma standartları konusunda uzman bir uyumluluk (compliance) asistanısın.
Kurallar:
1. YALNIZCA verilen KAYNAKLAR'daki bilgiye dayan. Kaynakta olmayan bir şeyi standart hükmü gibi sunma.
2. Her hükmü/iddiayı ilgili kaynağın numarasıyla köşeli parantez içinde belirt: [1], [2][4]. Numara uydurma.
3. Kaynaklar soruyu karşılamıyorsa bunu açıkça söyle ve hangi standarda bakılması gerektiğini (biliyorsan) öner.
4. Kullanıcının dilinde cevap ver (Türkçe soruya Türkçe). Standart kodlarını, madde numaralarını ve "shall/should"
   gibi zorunluluk ifadelerini koru; gerekirse kısa İngilizce terimi parantezde ver.
5. Biçim: önce 1-2 cümlelik doğrudan cevap, ardından gerekirse kısa madde işaretli liste ("- " ile).
   En fazla ~250 kelime. Başlık (#) kullanma; vurgu için **kalın** kullanabilirsin.
6. "shall" zorunlu, "should" tavsiye niteliğindedir; bu farkı önemliyse belirt."""


def generate_answer(question: str, sources: list[dict], history: list[dict], project: dict | None) -> str:
    s = get_settings()
    blocks = []
    for i, src in enumerate(sources, start=1):
        loc = f"{src['code']} {src['clause_ref']}".strip()
        head = f" — {src['heading']}" if src.get("heading") else ""
        blocks.append(f"[{i}] {loc}{head} (s. {src['page_start']})\n{src['content']}")
    proj = ""
    if project:
        proj = f"Kullanıcının projesi: {project['name']} — {project.get('description') or ''} (alanlar: {', '.join(project.get('domains') or [])})\n\n"
    hist = "\n".join(f"{m['role']}: {m['content'][:600]}" for m in history[-6:])
    prompt = (
        f"{proj}Önceki konuşma:\n{hist or '(yok)'}\n\n"
        f"KAYNAKLAR:\n\n" + "\n\n".join(blocks) + f"\n\nSORU: {question}"
    )
    return _generate(s.gemini_model, prompt, ANSWER_SYSTEM, temperature=0.2, max_tokens=2048)


def make_title(question: str) -> str:
    s = get_settings()
    if not s.llm_enabled:
        return _fallback_title(question)
    try:
        t = _generate(
            s.gemini_fast_model,
            f"Bu soru için 2-6 kelimelik Türkçe sohbet başlığı yaz, tırnak ve nokta kullanma:\n{question}",
            "Kısa başlık üretirsin.",
            temperature=0.3,
            max_tokens=40,
        )
        t = re.sub(r"\[\d+\]", "", t.strip().split("\n")[0]).strip().strip('"\'*#').rstrip(".").strip()[:60]
        return t or _fallback_title(question)
    except Exception:
        return _fallback_title(question)


def _fallback_title(q: str) -> str:
    q = " ".join(q.split())
    return q[:48] + ("…" if len(q) > 48 else "")
