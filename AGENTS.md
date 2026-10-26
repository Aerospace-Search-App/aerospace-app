# AGENTS.md — Yapay zekâ asistanları için (Codex, Cursor, Copilot ve diğerleri)

Havacılık/savunma standartlarına (MIL-STD-810H, MIL-STD-461G, DO-178C) RAG ile soru-cevap ve rapor uyumluluk
analizi yapan platformun mobil uygulamaya hizmet veren FastAPI API iskeleti (bugün mock bileşenlerle).

## Kod yazmadan önce oku (bağlayıcı)
1. `docs/BACKEND_GELISTIRME_REHBERI.md` — mimari, kurallar, PR süreci
2. `docs/API_CONTRACT.md` — API sözleşmesi, tek doğruluk kaynağı
3. `CLAUDE.md` — proje özeti ve komutlar

## Altın kurallar (ayrıntı: rehber §1)
1. Sözleşme önce: API'nin görünen hali önce `docs/API_CONTRACT.md`'de değişir, sonra kodda.
2. `src/domain/interfaces.py` imzalarını değiştirme, implemente et.
3. Bileşen (mock/gerçek) seçimi sadece `src/core/deps.py`'de.
4. Router'da iş mantığı ve try/except yok: doğrula → servisi çağır → şemayı döndür.
5. Hatalar `AppError` alt sınıflarıyla; servis `HTTPException` fırlatmaz, istemciye `str(e)` dönülmez.
6. Testler yeşil kalır; test silinmez, gevşetilmez, skip/xfail ile gizlenmez.
7. Yeni bağımlılık yalnızca PR'da gerekçeyle, `==` sürümle; `requirements.txt` CODEOWNERS onayı gerektirir.
8. `.env` asla commit edilmez; yeni ayar `src/core/config.py` + `.env.example`.
9. Kullanıcıya özel veri sahibine göre filtrelenir; başkasınınki `404`.
10. `main`'e doğrudan push yok; her şey PR ile, 2 onayla (hassas dosyalarda biri CODEOWNERS'tan).

## Komutlar
```bash
py -m venv .venv && .venv/Scripts/python -m pip install -r requirements.txt   # kurulum
.venv/Scripts/python -m pytest -q                                             # testler
.venv/Scripts/python -m uvicorn main:app --reload --port 8000                 # Swagger: /docs
```
PR öncesi `pytest -q` tamamen yeşil olmalı. PR şablonu: `.github/pull_request_template.md`.
