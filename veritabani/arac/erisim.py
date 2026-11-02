"""Kağan'ın API'si için veri tabanı erişim fonksiyonları.

Her fonksiyon bir SQLAlchemy bağlantısı (Connection) alır ve düz sözlük/liste döner.
Kullanım:
    from sqlalchemy import create_engine
    import erisim
    motor = create_engine(DATABASE_URL)
    with motor.begin() as c:
        sohbet = erisim.sohbet_ac(c, kullanici_id=1, baslik="Drone standartları")
"""
from sqlalchemy import text


def _liste(sonuc):
    return [dict(s._mapping) for s in sonuc]


def _tek(sonuc):
    s = sonuc.first()
    return dict(s._mapping) if s else None


# ---------- Standartlar ----------

def standartlari_listele(c, q=None, durum="ACTIVE", limit=20, offset=0):
    """Kod veya başlıkta arama yapar. Her standart için parça sayısı da döner."""
    return _liste(c.execute(
        text(
            """
            SELECT s.standard_id, s.code, s.title, s.version, s.issuing_body,
                   s.publication_year, s.status,
                   (SELECT count(*) FROM document_chunks d WHERE d.standard_id = s.standard_id) AS chunk_count
            FROM standards s
            WHERE (:durum IS NULL OR s.status = :durum)
              AND (:q IS NULL OR s.code ILIKE '%' || :q || '%' OR s.title ILIKE '%' || :q || '%')
            ORDER BY s.code, s.version
            LIMIT :limit OFFSET :offset
            """
        ),
        {"q": q, "durum": durum, "limit": limit, "offset": offset},
    ))


def standart_getir(c, standard_id):
    return _tek(c.execute(text("SELECT * FROM standards WHERE standard_id = :i"), {"i": standard_id}))


# ---------- Arama ----------

def kelime_ara(c, sorgu, limit=10):
    """Tam metin arama. 'ECSS-E-ST-32C 4.3.2' gibi kesin terimlerde iyi çalışır."""
    return _liste(c.execute(
        text(
            """
            SELECT d.chunk_id, d.standard_id, s.code, d.clause_number, d.page_number, d.content,
                   ts_rank(d.search_tsv, websearch_to_tsquery('english', :q)) AS score
            FROM document_chunks d JOIN standards s USING (standard_id)
            WHERE s.status = 'ACTIVE' AND d.search_tsv @@ websearch_to_tsquery('english', :q)
            ORDER BY score DESC
            LIMIT :limit
            """
        ),
        {"q": sorgu, "limit": limit},
    ))


def anlam_ara(c, vektor, limit=10):
    """Vektör (kosinüs) arama. vektor: 384 sayılık liste."""
    metin = "[" + ",".join(str(float(x)) for x in vektor) + "]"
    return _liste(c.execute(
        text(
            """
            SELECT d.chunk_id, d.standard_id, s.code, d.clause_number, d.page_number, d.content,
                   1 - (d.embedding <=> CAST(:v AS vector)) AS score
            FROM document_chunks d JOIN standards s USING (standard_id)
            WHERE s.status = 'ACTIVE' AND d.embedding IS NOT NULL
            ORDER BY d.embedding <=> CAST(:v AS vector)
            LIMIT :limit
            """
        ),
        {"v": metin, "limit": limit},
    ))


def hibrit_ara(c, sorgu, vektor, limit=5, k=60):
    """Kelime ve anlam sonuçlarını birleştirir (reciprocal rank fusion)."""
    siralar = {}
    for liste in (kelime_ara(c, sorgu, limit * 4), anlam_ara(c, vektor, limit * 4)):
        for sira, satir in enumerate(liste):
            kayit = siralar.setdefault(satir["chunk_id"], {**satir, "score": 0.0})
            kayit["score"] += 1.0 / (k + sira + 1)
    return sorted(siralar.values(), key=lambda x: x["score"], reverse=True)[:limit]


# ---------- Sohbet ----------

def sohbet_ac(c, kullanici_id, baslik=None):
    return _tek(c.execute(
        text("INSERT INTO chat_sessions (user_id, title) VALUES (:u, :t) RETURNING *"),
        {"u": kullanici_id, "t": baslik},
    ))


def sohbetleri_listele(c, kullanici_id, limit=50):
    return _liste(c.execute(
        text("SELECT * FROM chat_sessions WHERE user_id = :u ORDER BY session_id DESC LIMIT :l"),
        {"u": kullanici_id, "l": limit},
    ))


def sohbet_getir(c, session_id, kullanici_id):
    """Başkasının sohbetine erişilmesin diye kullanıcı kontrolü de yapar."""
    return _tek(c.execute(
        text("SELECT * FROM chat_sessions WHERE session_id = :s AND user_id = :u"),
        {"s": session_id, "u": kullanici_id},
    ))


def mesaj_ekle(c, session_id, gonderen, icerik):
    """gonderen: 'user' veya 'assistant'."""
    return _tek(c.execute(
        text("INSERT INTO messages (session_id, sender_type, content) VALUES (:s, :g, :i) RETURNING *"),
        {"s": session_id, "g": gonderen, "i": icerik},
    ))


def mesajlari_listele(c, session_id):
    return _liste(c.execute(
        text("SELECT * FROM messages WHERE session_id = :s ORDER BY message_id"), {"s": session_id}
    ))


def kaynak_ekle(c, message_id, kaynaklar):
    """Asistan cevabının dayandığı parçaları kaydeder.
    kaynaklar: [{'chunk_id', 'standard_id', 'clause_number', 'page_number', 'score'}, ...]"""
    if not kaynaklar:
        return 0
    c.execute(
        text(
            """
            INSERT INTO message_references
                (message_id, chunk_id, standard_id, clause_number, page_number, score)
            VALUES (:m, :chunk_id, :standard_id, :clause_number, :page_number, :score)
            """
        ),
        [{"m": message_id, "chunk_id": k.get("chunk_id"), "standard_id": k.get("standard_id"),
          "clause_number": k.get("clause_number"), "page_number": k.get("page_number"),
          "score": k.get("score")} for k in kaynaklar],
    )
    return len(kaynaklar)


def kaynaklari_getir(c, message_id):
    return _liste(c.execute(
        text(
            """
            SELECT r.*, s.code, s.title
            FROM message_references r LEFT JOIN standards s USING (standard_id)
            WHERE r.message_id = :m ORDER BY r.reference_id
            """
        ),
        {"m": message_id},
    ))


# ---------- Kaydedilen standartlar ----------

def standart_kaydet(c, kullanici_id, standard_id):
    """İkinci kez kaydedilirse hata vermez, sessizce geçer."""
    c.execute(
        text("INSERT INTO saved_standards (user_id, standard_id) VALUES (:u, :s) ON CONFLICT DO NOTHING"),
        {"u": kullanici_id, "s": standard_id},
    )


def standart_kaydini_sil(c, kullanici_id, standard_id):
    c.execute(
        text("DELETE FROM saved_standards WHERE user_id = :u AND standard_id = :s"),
        {"u": kullanici_id, "s": standard_id},
    )


def kaydedilenleri_listele(c, kullanici_id):
    return _liste(c.execute(
        text(
            """
            SELECT s.*, v.saved_at FROM saved_standards v JOIN standards s USING (standard_id)
            WHERE v.user_id = :u ORDER BY v.saved_at DESC
            """
        ),
        {"u": kullanici_id},
    ))
