# Görev: API İskeleti (Swagger) + Sunum PDF'i — Sahip: Kağan Bayrak

> **Durum: tamamlandı (27 Ekim 2026).** Bu doküman ilk iterasyonun planıdır ve referans olarak tutulur.
> İçinde geçen `manager` ajanı ve `docs/OGRENME_NOTLARI.md`, Kağan'ın lokal çalışma düzenine aittir; repoda yer almaz.
> Güncel ekip kuralları: `docs/BACKEND_GELISTIRME_REHBERI.md`.

**Hedef:** 20 endpoint'lik çekirdek API Swagger'da görünür, şemalı ve örnekli olsun; mock modda uçtan uca
çalışsın; ekip arkadaşlarının parçalarını takacağı yerler net olsun. Ardından bu iş, Swagger ekran
görüntüleriyle birlikte **5–10 sayfalık Türkçe PDF**'e dönüşsün.
**Son tarih: 27 Ekim 2026 akşamı (ders sunumu).** Önce çalışan iskelet, sonra PDF, en son cila.

## Temel kararlar
1. **Sıfırdan, temiz proje.** Eski repo sadece referans (`docs/REPO_ANALYSIS.md` oradaki hataları listeler — tekrarlama).
2. **Mock-first, DB'siz:** Repository'ler, arama ve LLM bellek-içi mock. Uygulama her başladığında 3 örnek standartla
   (MIL-STD-810H, MIL-STD-461G, DO-178C) dolu gelir. Gerçek implementasyonlar ekip arkadaşlarından gelecek.
3. **Auth = Taha'nın mevcut hali:** yollar `/auth/*` (prefix yok), şemalar aşağıdaki gibi. Davranış stub
   (sahte token). PDF'te "birleştirmede `/api/v1` altına alınacak" diye not düşülür.
4. **Sözleşme önce:** Şemalar `docs/API_CONTRACT.md`'den gelir.

## Çekirdek endpoint seti (20)
| # | Metot | Yol | Başarı | Grup (tag) | Takma noktası |
|---|---|---|---|---|---|
| 1 | GET | `/` | 200 | System | – |
| 2 | GET | `/health` | 200 | System | arama/LLM adı gösterilir |
| 3 | GET | `/api/v1/meta/enums` | 200 | System | – |
| 4 | POST | `/auth/register` | 201 | Auth | Taha |
| 5 | POST | `/auth/login` | 200 | Auth | Taha |
| 6 | POST | `/auth/refresh` | 200 | Auth | Taha |
| 7 | GET | `/auth/me` | 200 | Auth | Taha |
| 8 | GET | `/api/v1/standards` | 200 | Standards | Doruk (repository) |
| 9 | POST | `/api/v1/standards` | 201 | Standards | Doruk |
| 10 | GET | `/api/v1/standards/{standard_id}` | 200 | Standards | Doruk |
| 11 | POST | `/api/v1/standards/{standard_id}/document` | 202 | Standards | Onur (PDF'ler), Sudenur (parçalama) |
| 12 | GET | `/api/v1/standards/{standard_id}/index-status` | 200 | Standards | Sudenur |
| 13 | POST | `/api/v1/search` | 200 | Search & Chat | Sudenur (hibrit arama) |
| 14 | POST | `/api/v1/chat/ask` | 200 | Search & Chat | Sudenur + LLM, Onur (web sohbet) |
| 15 | GET | `/api/v1/chat/conversations` | 200 | Search & Chat | Doruk |
| 16 | GET | `/api/v1/chat/conversations/{conversation_id}` | 200 | Search & Chat | Doruk |
| 17 | POST | `/api/v1/reports` | 202 | Reports | – |
| 18 | GET | `/api/v1/reports` | 200 | Reports | Doruk |
| 19 | GET | `/api/v1/reports/{report_id}` | 200 | Reports | Doruk |
| 20 | POST | `/api/v1/reports/{report_id}/analyses` | 201 | Reports | LLM |

Şemalar ve hata kodları: `docs/API_CONTRACT.md` (auth için §3'teki "Bu hafta: Taha'nın şekli" kutusu).

## Hedef dosya yapısı
```
main.py                         # create_app() (uvicorn main:app)
requirements.txt  .env.example  .gitignore  README.md
src/
  core/      config.py  errors.py  deps.py  security.py (stub, TODO Taha)  logging.py
  domain/    enums.py  entities.py  interfaces.py   # Protocol'ler: repository'ler, SearchService, LLMClient, FileStorage
  application/
    schemas/   common.py (Page, ErrorResponse)  auth.py  standard.py  search.py  chat.py  report.py  meta.py
    services/  standards_service.py  chat_service.py  report_service.py  analysis_service.py  auth_service.py (stub)
  infrastructure/
    memory/    repositories.py  seed.py      # bellek-içi repository'ler + 3 örnek standart
    search/    mock_search.py                # deterministik sahte kaynaklar (MIL-STD-810H Method 514.8 vb.)
    llm/       mock_llm.py                   # "[DEMO]" ile başlayan deterministik cevap/karar
    storage/   local_storage.py              # uuid adla ./storage'a yazar, %PDF + boyut kontrolü
  api/
    system.py  auth.py
    v1/  __init__.py (prefix=/api/v1)  meta.py  standards.py  search.py  chat.py  reports.py
tests/
  conftest.py  api/test_contract_coverage.py  test_system.py  test_auth.py  test_standards.py  test_chat.py  test_reports.py
tools/
  screenshots.py                # Playwright (channel="msedge" veya "chrome"): Swagger ekran görüntüleri
  build_pdf.py                  # docs/rapor/rapor.html → docs/rapor/Kagan_Bayrak_API_Iskeleti.pdf
docs/rapor/  rapor.html  img/*.png  Kagan_Bayrak_API_Iskeleti.pdf
docs/OGRENME_NOTLARI.md
```

## Fazlar
Her faz: backend-developer yapar → tester doğrular → manager Kağan'a "ne/neden/sorulursa" anlatır,
`docs/OGRENME_NOTLARI.md`'ye ekler → Kağan onaylarsa commit.

### Faz 0 — Hazırlık (~15 dk)
- `.venv` oluştur, `requirements.txt` (fastapi, uvicorn[standard], pydantic, pydantic-settings, python-multipart,
  loguru, pytest, httpx, playwright) — Python 3.14'te kurulabilen güncel sürümler, kurulumdan sonra sabitlenir.
- `.gitignore` (.venv, .env, storage/, __pycache__, .pytest_cache), `.env.example`, kısa `README.md`.
- ✅ `pip install` hatasız, `pytest` çalışıyor (0 test olabilir).

### Faz 1 — Çekirdek (~30 dk)
- `core/config.py`, `core/errors.py` (+ 422 dahil tek tip hata handler'ı), `core/deps.py`, `main.py` → `create_app()` + lifespan.
- `GET /`, `/health`, `/api/v1/meta/enums`. Swagger başlığı, açıklaması (Türkçe), tag açıklamaları, HTTPBearer ("Authorize" butonu).
- ✅ `/docs` açılıyor, 3 endpoint çalışıyor, bilinmeyen yol `{"error": {...}}` dönüyor.

### Faz 2 — Şemalar (~30 dk)
- `application/schemas/*` + `domain/enums.py` — 20 endpoint'in tüm istek/cevap şemaları, örnek değerlerle.

### Faz 3 — Router'lar + mock servisler (~60 dk)
- 20 endpoint, servisler, bellek-içi repository'ler, mock arama/LLM, seed verisi.
- PDF yükleme 202 → arka planda `PENDING → INDEXED`; rapor yükleme 202 → `READY`.
- `# TODO(Taha|Doruk|Sudenur)` işaretleri takma noktalarında.
- ✅ Swagger'dan her endpoint 2xx dönebiliyor.

### Faz 4 — Testler (~30 dk)
- Tester: sözleşme kapsama testi (20 çift), her endpoint için mutlu yol + en az 1 hata yolu, hata formatı, sayfalama.
- ✅ `pytest -q` yeşil.

### Faz 5 — Sunum PDF'i (~60–90 dk)
> **Güncelleme (26 Ekim, Kağan'ın kararı):** PDF **10–12 sayfa**; Taha'nın görünümünü birebir izlemek zorunlu değil —
> daha modern ve okunabilir tasarım serbest. İçerik kaynağı: `docs/rapor/RAPOR_METNI.md`. 12 ekran görüntüsü.
> Aşağıdaki "5–10 sayfa" ve "Taha'nınkiyle aynı görünüm" ifadeleri bu güncellemeyle geçersiz.
1. **Ekran görüntüleri** (`tools/screenshots.py`, sunucu arka planda çalışırken): Swagger genel görünüm (tüm gruplar),
   `/health` cevabı, standart listeleme, standart ekleme (201), aynı kodla tekrar ekleme (409 → hata formatı),
   PDF yükleme (202) + index-status (`INDEXED`), `chat/ask` kaynaklı cevap, rapor analizi (201). Yüksek çözünürlük, okunur yazı.
2. **İçerik** (`docs/rapor/rapor.html`) — Taha'nın PDF'iyle aynı iskelet ve görünüm (lacivert başlıklı tablolar, mavi başlıklar, A4):
   - Kapak satırı: "API İskeleti (Swagger) — Kağan Bayrak", ders/proje adı, tarih
   1. Ne yaptım? (3–4 cümle, sade)
   2. Kullanılan teknolojiler (tablo: Teknoloji | Ne işe yarıyor?)
   3. Sistem nasıl çalışıyor? (katman şeması + "bir isteğin yolculuğu" adım tablosu: Mobil → Router → Servis → Mock/Gerçek)
   4. API uç noktaları (20 satırlık tablo, gruplu: Yöntem | Adres | Görevi)
   5. Ekip arkadaşlarının modülleri nereye takılıyor? (tablo: Kişi | Görevi | İskeletteki yeri)
   6. Ortak kurallar: `/api/v1` sürümleme (neden), tek tip hata formatı, sayfalama, 202 + durum sorgulama
   7. Swagger ile test (ekran görüntüleri, "Şekil N – ..." altyazılarıyla, her birinin altında 1–2 cümle açıklama)
   8. Mobil ekip için bağlanma notları (emülatör `10.0.2.2:8000`, gerçek cihaz LAN IP) + sonraki adımlar
   - Auth notu: "Auth uçları Taha'nın modülünün şu anki halini gösterir (`/auth/*`); birleştirmede `/api/v1/auth/*` olacak."
3. **PDF** (`tools/build_pdf.py`, Playwright `page.pdf`, A4, kenar boşlukları, sayfa numarası) →
   `docs/rapor/Kagan_Bayrak_API_Iskeleti.pdf`. **5–10 sayfa.**
4. ✅ Tester: sayfa sayısı 5–10, tüm görseller görünüyor, Türkçe karakterler doğru, endpoint tablosu kodla birebir.
5. PDF'in bir kopyası masaüstüne (`~/Desktop/Kagan_Bayrak_API_Iskeleti.pdf`).

**Zaman yetmezse kesme sırası:** Faz 4'te sadece kapsama + mutlu yol testleri; Faz 5'te ekran görüntüsü sayısı 5'e iner.
PDF asla kesilmez — teslim edilen şey o.

## Kabul kriterleri (Definition of Done)
- [ ] 20 endpoint Swagger'da; her biri `summary`, tag, `response_model`, örnekli şema ve hata cevaplarıyla
- [ ] `test_contract_coverage.py` geçiyor (yukarıdaki tablo ↔ kod birebir)
- [ ] Tüm hata cevapları `{"error": {...}}` formatında
- [ ] `.env` olmadan uygulama ayağa kalkıyor, tüm endpoint'ler 2xx dönebiliyor
- [ ] `pytest -q` yeşil
- [ ] PDF 5–10 sayfa, Türkçe, Taha'nınkiyle aynı yapıda, masaüstünde
- [ ] `docs/OGRENME_NOTLARI.md` her fazı kapsıyor; Kağan sunum sorularına hazır

## Ekibe duyuru şablonu (Faz 3 sonunda, isteğe bağlı)
> API iskeleti hazır. Swagger: `http://<IP>:8000/docs`. Sözleşme: `docs/API_CONTRACT.md`.
> Taha → `src/core/security.py` + `auth_service.py` (`AUTH_ENABLED=true` yapınca devreye girer)
> Doruk → repository arayüzleri (`src/domain/interfaces.py`), şu an bellek-içi
> Sudenur → `SearchService` arayüzü, şu an `mock_search.py`
> Onur → PDF yükleme `POST /api/v1/standards/{id}/document`, sohbet `POST /api/v1/chat/ask`
> Şeyma & Ammar → base URL config'de; mock modda bütün ekranlar veri alır
