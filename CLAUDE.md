# CLAUDE.md — Aerospace Compliance Platform · Mobil API İskeleti

Bu dosya Claude Code'un bu repoda her oturumda okuduğu proje kurallarıdır. Kısa tut, güncel tut.

## Proje bir cümlede
Havacılık/savunma standartlarına (MIL-STD-810H, MIL-STD-461G, DO-178C) RAG ile soru-cevap ve
teknik rapor uyumluluk analizi yapan platformun, 7 kişilik ekibin geliştirdiği **mobil uygulamaya**
hizmet verecek **API iskeleti (Swagger)**. Proje ekibe aittir; herkes `docs/BACKEND_GELISTIRME_REHBERI.md`'ye göre katkı verir.

## Durum (27 Ekim 2026)
- 20 endpoint'lik çekirdek API iskeleti tamam; mock (bellek-içi) bileşenlerle uçtan uca çalışıyor, 652 test yeşil.
- Sunum PDF'i: `docs/rapor/` (kaynak `RAPOR_METNI.md`, üretim `tools/`).
- Sıradaki: ekip arkadaşlarının gerçek bileşenleri takması (`docs/BACKEND_GELISTIRME_REHBERI.md` §5) ve sözleşmedeki kalan 12 endpoint.

Detaylı bilgi:
- `docs/BACKEND_GELISTIRME_REHBERI.md` — ekip için bağlayıcı backend kuralları ve PR süreci
- `docs/TASK_API_SKELETON.md` — ilk iterasyonun görev planı (tamamlandı; referans)
- `docs/API_CONTRACT.md` — tam sözleşme (32 endpoint); bu hafta sadece §0.1'deki çekirdek set uygulanır
- `docs/PROJECT_OVERVIEW.md` — alan bilgisi, RAG akışı, ekip
- `docs/REPO_ANALYSIS.md` — **sadece referans**: eski repodaki hatalar (bu projede o kod yok, aynı hataları tekrarlamamak için okunur)

Eski repo (`github.com/onurcansari/aerospace-compliance-platform`) **sadece okunur referanstır**.
Oradan kod kopyalanmaz, oraya commit atılmaz. Bu proje sıfırdan, temiz yazılır.

## Teknoloji
Python 3.14 (makinede kurulu olan) · FastAPI · Pydantic v2 · pydantic-settings · Loguru · pytest + httpx ·
Playwright (sadece Swagger ekran görüntüsü + PDF üretimi için, sistemdeki Edge/Chrome ile).
**Şimdilik veritabanı, ChromaDB ve Gemini yok:** her dış bağımlılık bir arayüzün arkasında, şimdilik
**bellek-içi (in-memory) mock** implementasyonla çalışır. Ekip arkadaşları gerçeğini sonra takar.

## Komutlar
Komutları **Bash aracıyla (Git Bash)** çalıştır; izinler `.claude/settings.json`'da Bash için tanımlı.
Sanal ortam `.venv` (Windows yolu `.venv/Scripts/`):
```bash
py -m venv .venv                                    # bir kez
.venv/Scripts/python -m pip install -r requirements.txt
.venv/Scripts/python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000   # Swagger: http://localhost:8000/docs
.venv/Scripts/python -m pytest -q                   # tüm testler
.venv/Scripts/python -m pytest tests/api -q         # sadece API testleri
```

## Mimari kuralları (Clean Architecture — bozma)
```
main.py            create_app() çağırır (uvicorn main:app)
src/
  domain/          entity'ler + enum'lar + arayüzler (Protocol). Dış kütüphane import ETMEZ.
  application/     services/ (iş mantığı) + schemas/ (Pydantic istek/cevap = API sözleşmesi)
  infrastructure/  arayüzlerin implementasyonları: memory/ (repository'ler), search/, llm/, storage/ — şimdilik mock
  api/             routers: system.py, auth.py (Taha'nın şekli), v1/ (standards, search, chat, reports)
  core/            config, logging, hata tipleri + handler'lar, deps (get_*_service, get_current_user)
tools/             Swagger ekran görüntüsü ve PDF üretim script'leri (uygulama kodu değil)
docs/rapor/        PDF'in kaynağı (HTML + görseller) ve çıktısı
```
- Router içinde iş mantığı **yok**: doğrula → servisi çağır → şemayı dön.
- Servisler somut sınıfa değil arayüze bağımlıdır (`SearchService`, `LLMClient`, `FileStorage`, repository arayüzleri).
  Hangi implementasyonun kullanılacağı `src/core/deps.py` içinde seçilir. Bu "takma noktaları" sunumun ana mesajı.
- Ağır/paylaşılan nesneler (repository'ler, arama, LLM) istek başına oluşturulmaz; uygulama başlarken (lifespan) bir kez.
- Uzun işler (PDF indeksleme, rapor işleme) `BackgroundTasks` ile yapılır, endpoint `202` döner.

## API kuralları
- Endpoint'ler `/api/v1` altında. İstisnalar: sistem (`/`, `/health`) ve **auth (`/auth/*`, Taha'nın mevcut hali;
  birleştirmede tek satırla `/api/v1` altına alınacak)**.
- Her endpoint'te: `response_model`, `status_code`, `summary`, `description`, `tags`, hata cevapları (`responses=`).
- Her şemada `Field(examples=...)` / `json_schema_extra` ile örnek değer. Swagger mobil ekibin dokümanıdır ve PDF'teki ekran görüntüleri buradan alınır.
- Liste endpoint'leri sayfalı: `?page=1&page_size=20` → `{items, total, page, page_size}`.
- Hata formatı tek tip: `{"error": {"code": "NOT_FOUND", "message": "...", "details": null}}` (422 dahil).
  Servisler `AppError` alt sınıfları fırlatır; global handler HTTP koduna çevirir. İstemciye ham `str(e)` / stack trace dönülmez.
- Tarihler ISO 8601 UTC (`datetime.now(timezone.utc)`). Enum değerleri büyük harf string.
- Sözleşme değişirse önce `docs/API_CONTRACT.md`, sonra kod (süreç: `docs/BACKEND_GELISTIRME_REHBERI.md` §12).

## Güvenlik
- `.env` okunmaz, commit edilmez, içeriği yazdırılmaz. Ayarlar `.env.example` üzerinden belgelenir.
- Yüklenen dosya adı diske kullanılmaz: `uuid4().hex + ".pdf"`. PDF doğrulama: uzantı + ilk baytlar `%PDF` + boyut sınırı.
- Auth: `get_current_user` dependency'si. `AUTH_ENABLED=false` iken demo kullanıcı döner (Taha gerçeğini bağlayana kadar).

## Ekip ve görev dağılımı
Herkes kendi parçasını rehber §5'teki takma noktalarına bağlar; birleştirme 2 onayla yapılır.

| Kişi | Görevi | İskelette ona ayrılan yer |
|---|---|---|
| Kağan | API iskeleti (Swagger) | iskelet geneli: router'lar, şemalar, servisler, sözleşme |
| Taha | Kayıt/giriş, JWT | `src/api/auth.py`, `auth_service.py`, `core/security.py` → `# TODO(Taha)` |
| Doruk | PostgreSQL şeması, chunk yükleme/sorgu | repository arayüzleri → `# TODO(Doruk)` |
| Sudenur | Madde bazlı parçalama, hibrit arama, kaynaklı cevap | `SearchService` arayüzü → `# TODO(Sudenur)` |
| Onur | Standart PDF'leri, web yükleme, sohbetin API'ye bağlanması | `POST /standards/{id}/document`, `POST /chat/ask` |
| Şeyma, Ammar | Mobil iskelet, giriş/kayıt ve sohbet ekranları | Swagger + `docs/API_CONTRACT.md` §7 |

## Git
- Repo GitHub'da; `main` korumalı: doğrudan push yok, her değişiklik PR ile.
- Birleştirme için 2 onay gerekir; hassas dosyalarda (sözleşme, arayüzler, bağımlılıklar, CI) onaylardan biri `.github/CODEOWNERS`'taki sahiplerden olmalı. Ayrıntı: `docs/BACKEND_GELISTIRME_REHBERI.md` §11.
- Dal adı `<isim>/<kısa-konu>`; Conventional Commits: `feat(api): ...`, `fix(search): ...`, `test(api): ...`, `docs: ...`, `chore: ...`
- PR öncesi `pytest -q` yeşil olmalı (GitHub Actions da her PR'da çalıştırır).

## Dil
- Kod, değişken, endpoint, şema adları: İngilizce.
- Dokümanlar, PDF, kullanıcıya dönen hata mesajları, commit açıklamaları: Türkçe.
- Türkçe metinlerde Kiril/benzer karakter karışmasın.
