# Aerospace Compliance Platform — Mobil API İskeleti

Havacılık/savunma standartlarına (MIL-STD-810H, MIL-STD-461G, DO-178C) RAG ile soru-cevap ve teknik rapor
uyumluluk analizi yapan platformun, mobil uygulamaya hizmet veren FastAPI iskeleti (Swagger + mock veriler).

## Kurulum
```bash
py -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt
```
`.env` dosyası **opsiyoneldir**; tüm ayarlar ve varsayılanları `.env.example`'da açıklanmıştır.

## Çalıştırma
```bash
.venv/Scripts/python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
```
- Swagger: <http://localhost:8000/docs>
- OpenAPI JSON: <http://localhost:8000/openapi.json>
- Android emülatörden: `http://10.0.2.2:8000`, gerçek cihazdan: bilgisayarın LAN IP'si

## Test
```bash
.venv/Scripts/python -m pytest -q
```

## Klasör yapısı
```
main.py            create_app() çağırır (uvicorn main:app)
src/
  domain/          entity'ler + enum'lar + arayüzler (Protocol). Dış kütüphane import etmez.
  application/     services/ (iş mantığı) + schemas/ (Pydantic istek/cevap = API sözleşmesi)
  infrastructure/  arayüzlerin implementasyonları: memory/, search/, llm/, storage/ — şimdilik mock
  api/             routers: system.py, auth.py, v1/ (standards, search, chat, reports)
  core/            config, logging, hata tipleri + handler'lar, deps (get_*_service, get_current_user)
tools/             Swagger ekran görüntüsü ve PDF üretim script'leri
docs/              sözleşme (API_CONTRACT.md), görev planı, rapor
```

Tüm hata cevapları tek tip: `{"error": {"code": "NOT_FOUND", "message": "...", "details": null}}`.
Ayrıntılı sözleşme: `docs/API_CONTRACT.md`.

## Katkı / Ekip için
Kod yazmadan önce: [docs/BACKEND_GELISTIRME_REHBERI.md](docs/BACKEND_GELISTIRME_REHBERI.md) (bağlayıcı kurallar, PR süreci),
[docs/API_CONTRACT.md](docs/API_CONTRACT.md) (API sözleşmesi) ve [CONTRIBUTING.md](CONTRIBUTING.md) (dal, commit, PR).
