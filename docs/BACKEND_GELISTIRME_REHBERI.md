# Backend Geliştirme Rehberi — Aerospace Compliance Platform (Mobil API)

> **Bu backend'de kod yazan herkes (ve kullandığı yapay zekâ asistanı) bu dosyaya uyar.**
> Amaç: Herkes farklı bir kafayla ilerleyip API'yi bozmasın; mobil ekip (Şeyma, Ammar) ve web (Onur)
> hiçbir şey değişmeden gerçek bileşenlere geçebilsin.
>
> Sahibi: tüm ekip · Son güncelleme: 27 Ekim 2026
> Bu rehberle çelişen bir kod/PR görürsen PR'da belirt; rehberi değiştirmek de bir PR'dır (bkz. §11).

---

## 0. Yapay zekâ asistanı kullanıyorsan önce bunu oku

Asistanına (Claude Code, Cursor, Copilot, ChatGPT...) **her yeni oturumda** şu metni ver:

```
Bu repoda backend geliştiriyorum. Kod yazmadan önce şu dosyaları oku ve kurallarına birebir uy:
1) docs/BACKEND_GELISTIRME_REHBERI.md   (mimari, kurallar, PR süreci — bağlayıcı)
2) docs/API_CONTRACT.md                 (API sözleşmesi — tek doğruluk kaynağı)
3) CLAUDE.md                            (proje özeti ve komutlar)
Kurallar:
- Sözleşmede (API_CONTRACT.md) olmayan endpoint/alan ekleme, var olanı silme veya adını değiştirme.
- Sadece benim görevimle ilgili dosyalara dokun; ilgisiz dosyaları yeniden düzenleme/biçimlendirme.
- Yeni bağımlılık ekleme ihtiyacı varsa önce bana sor, gerekçesini yaz.
- Mevcut testleri silme, gevşetme veya atlama (skip/xfail) yapma.
- Bitirmeden önce `.venv/Scripts/python -m pytest -q` çalıştır; hepsi yeşil olmalı.
- Emin olmadığın yerde tahmin etme; dosyayı oku ya da bana sor.
Görevim: <buraya kendi görevini yaz>
```

Asistanın ürettiği her değişikliği **kendin okuyup anlamadan** PR'a koyma. PR'ın sahibi sensin, asistan değil.

---

## 1. Altın kurallar (ihlali = PR reddedilir)

| # | Kural | Neden |
|---|---|---|
| 1 | **Sözleşme önce.** API'nin görünen hali (yol, metot, status kodu, alan adı/tipi, enum değeri, hata kodu) `docs/API_CONTRACT.md`'de yazar. Değişiklik önce oraya, sonra koda. | Mobil uygulama bu belgeye göre yazılıyor; sessiz değişiklik ekranı bozar. |
| 2 | **Arayüzü (Protocol) değiştirme, implemente et.** `src/domain/interfaces.py` imzaları sabittir. Değişmesi gerekiyorsa PR'da gerekçeyle öner. | Herkesin parçası bu arayüzlere bağlı; imza değişirse başkasının kodu kırılır. |
| 3 | **Bileşen seçimi sadece `src/core/deps.py`'de.** Mock → gerçek geçişi orada yapılır; servis/router içinde somut sınıf `import` edilmez. | Takma noktası tek yerde kalır; geri almak tek satırdır. |
| 4 | **Router'da iş mantığı yok.** Router: doğrula → servisi çağır → şemayı döndür. try/except yok. | Kurallar servislerde toplanır, test edilebilir kalır. |
| 5 | **Hatalar `AppError` alt sınıflarıyla.** Servis `HTTPException` fırlatmaz, istemciye `str(e)` dönülmez. | Tek tip hata formatı (`{"error": {...}}`) bozulmaz, iç bilgi sızmaz. |
| 6 | **Testler yeşil, sözleşme kapsama testi yeşil.** Test silinmez, gevşetilmez. | 652 test, sözleşmenin koddaki bekçisi. |
| 7 | **Yeni bağımlılık = PR'da gerekçe + CODEOWNERS onayı.** Sürüm `==` ile sabitlenir. | Ağır/kullanılmayan bağımlılık eski repoda sorun çıkardı. |
| 8 | **`.env` asla commit edilmez.** Yeni ayar → `src/core/config.py` + `.env.example`. | Gizli anahtarlar (Gemini, JWT secret) repoya düşmez. |
| 9 | **Kullanıcıya özel veri sahibine göre filtrelenir; başkasınınki `404`.** | Kaydın varlığı sızdırılmaz. |
| 10 | **`main`'e doğrudan push yok.** Her şey PR ile, 2 onayla (hassas dosyalarda biri CODEOWNERS'tan). | Tek kişinin gözünden kaçan hata ikinci kişiye takılır; iskeletin bütünlüğü korunur. |

---

## 2. Tek doğruluk kaynakları

| Dosya | Ne için? | Kim değiştirir? |
|---|---|---|
| `docs/API_CONTRACT.md` | Endpoint'ler, şemalar, hata kodları, enum'lar | PR + 2 onay, biri CODEOWNERS (§12) |
| `docs/BACKEND_GELISTIRME_REHBERI.md` (bu dosya) | Mimari, kod kuralları, PR süreci | PR + 2 onay, biri CODEOWNERS |
| `src/domain/interfaces.py` | Takma noktalarının imzaları | PR + 2 onay, biri CODEOWNERS; etkilenen kişiler PR'da etiketlenir |
| `src/core/deps.py` | Hangi implementasyonun kullanıldığı | Takan kişi, kendi satırı |
| `tests/api/test_contract_coverage.py` | 20 endpoint'in sabit listesi | Sözleşme değişikliğiyle birlikte |
| `CLAUDE.md`, `AGENTS.md` | Proje özeti, komutlar (AI asistanları okur) | PR + 2 onay, biri CODEOWNERS |

**Çelişki olursa:** `API_CONTRACT.md` > bu rehber > koddaki yorumlar.

---

## 3. Kurulum ve komutlar

Python **3.14** kullan (bağımlılıklar bu sürümle sabitlendi). Komutlar Windows (Git Bash / PowerShell):

```bash
py -m venv .venv                                         # bir kez
.venv/Scripts/python -m pip install -r requirements.txt  # bağımlılıklar
.venv/Scripts/python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000   # sunucu
.venv/Scripts/python -m pytest -q                        # tüm testler (PR öncesi zorunlu)
```
- Swagger: `http://localhost:8000/docs` · OpenAPI JSON: `/openapi.json`
- `.env` opsiyonel; tüm ayarlar ve varsayılanları `.env.example`'da.
- Veriler bellekte (mock modda): sunucu yeniden başlayınca başlangıç verisine (3 standart, 1 rapor, demo kullanıcı) döner.

**Ayarlar (`src/core/config.py`)**

| Ayar | Varsayılan | Not |
|---|---|---|
| `AUTH_ENABLED` | `false` | `false` iken her istek demo kullanıcı (id=1, ADMIN) |
| `SEARCH_PROVIDER` | `mock` | Başka değer şu an açılışta hata verir → Sudenur ekleyecek |
| `LLM_PROVIDER` | `mock` | Başka değer → LLM çağrıları `LLM_UNAVAILABLE` (Gemini bağlanana kadar) |
| `GEMINI_API_KEY`, `GEMINI_MODEL` | –, `gemini-2.5-flash` | Gemini istemcisi için |
| `MAX_UPLOAD_MB` | `50` | Hem doğrulama hem `/meta/enums` bu ayarı okur |
| `STORAGE_DIR` | `./storage` | Yüklenen PDF'ler (git'e girmez) |
| `CORS_ORIGINS`, `LOG_LEVEL` | `["*"]`, `INFO` | |

Yeni ayar eklerken: `Settings`'e alan + `.env.example`'a satır + açıklama. Kodun hiçbir yerinde `os.environ` / `load_dotenv` kullanılmaz; ayar `get_settings()` (veya `Depends(get_settings)`) ile alınır.

---

## 4. Mimari

### 4.1 Katmanlar ve import kuralları

```
main.py            create_app() — uygulama fabrikası, lifespan, hata handler'ları, router kaydı
src/
  api/             HTTP katmanı: router'lar (system.py, auth.py, v1/*.py), responses.py (hata dokümanı yardımcısı)
  application/     schemas/ (Pydantic istek/cevap = sözleşmenin koddaki hali) + services/ (iş kuralları)
  domain/          entities.py (dataclass), enums.py, interfaces.py (Protocol). Dış kütüphane import ETMEZ.
  infrastructure/  arayüz implementasyonları: memory/ (repository + seed), search/, llm/, storage/
  core/            config.py, errors.py, deps.py, security.py, logging.py
tests/api/         API testleri (TestClient)
tools/             ekran görüntüsü / PDF script'leri (uygulama kodu değil)
```

| Katman | Kimi import edebilir? | Kimi import EDEMEZ? |
|---|---|---|
| `domain` | sadece standart kütüphane + kendi içi | FastAPI, Pydantic, `application`, `infrastructure`, `api`, `core` |
| `application/services` | `domain`, `application/schemas`, `core/errors` | `infrastructure` (somut sınıflar), `api`, FastAPI (`Request`, `HTTPException`) |
| `application/schemas` | `domain/enums`, Pydantic | `infrastructure`, `api`, servisler |
| `infrastructure` | `domain`, `core/errors`, kendi kütüphaneleri (DB sürücüsü, arama, Gemini SDK) | `api`, servisler |
| `api` | `application`, `core/deps`, `core/errors`, `api/responses` | `infrastructure` (doğrudan) |
| `core/deps.py` | hepsi (bileşenleri burada birleştirir) | – |

### 4.2 Bir isteğin yolu
```
Mobil → router (şema doğrulama; hatalıysa otomatik 422)
      → servis (iş kuralı; hata ise AppError)
      → arayüz (repository / SearchService / LLMClient / FileStorage)
      → implementasyon (bugün mock, yarın gerçek — deps.py seçer)
      ← servis entity döner ← router `XxxOut.model_validate(entity)` ile şemaya çevirir
```

### 4.3 Paylaşılan nesneler bir kez oluşturulur
Repository'ler, arama, LLM ve dosya deposu `init_app_state()` içinde (lifespan, uygulama açılışında) **bir kez**
oluşturulup `app.state`'e konur. `get_*_service(request)` fonksiyonları her istekte bu hazır nesnelerden hafif
servis nesneleri kurar. **İstek başına DB bağlantı havuzu, embedding modeli, Gemini istemcisi oluşturulmaz.**

### 4.4 Uzun işler: `BackgroundTasks` + `202`
PDF indeksleme ve rapor işleme arka planda yapılır; endpoint hemen `202` + durum (`PENDING` / `UPLOADED`) döner,
mobil durum endpoint'ini yoklar. Arka plan fonksiyonu:
- Hata olursa durumu `FAILED` + `error_message` olarak **kaydeder** (hata durumu kaybolmaz),
- İç hata ayrıntısını `error_message`'a yazmaz (kullanıcıya genel mesaj, ayrıntı log'a),
- **Doruk için:** gerçek DB'de arka plan görevi istek oturumunu (session) kullanamaz; kendi oturumunu açıp kapatmalıdır.

---

## 5. Takma noktaları — kim, nereye, nasıl?

Ortak kural: **Arayüzü implemente et → `deps.py`'de seç → mevcut testler yeşil kalsın → kendi testlerini ekle.**
Koddaki yerin `TODO(Adın)` ile işaretli: `grep -rn "TODO(Doruk)" src` gibi.

### 5.1 Doruk — PostgreSQL repository'leri
- **Arayüzler:** `StandardRepository`, `ConversationRepository`, `ReportRepository`, `AnalysisRepository`, `UserRepository` (`src/domain/interfaces.py`).
- **Yer:** Yeni modül `src/infrastructure/db/` (ör. `repositories.py`, `models.py`, `session.py`). `memory/` silinmez (testler ve demo kullanır).
- **Seçim:** `init_app_state()` içindeki `InMemory*Repository()` satırları; bir ayarla (ör. `DATABASE_URL` / `STORAGE_BACKEND`) mock ↔ gerçek seçilebilir olmalı.
- **Uyulması gerekenler (mevcut davranış, testlerle korunuyor):**
  - `find` / `list_by_user` → `(items, total)` döner; `offset`/`limit` uygular; sıralama arayüz docstring'indeki gibi (standartlar id sırasıyla, sohbet/rapor en yeni önce).
  - `q` araması büyük/küçük harf, Türkçe harf (İ/ı/I/i) ve aksan duyarsız (`TİTREŞİM` = `titreşim` = `titresim`). Postgres'te `unaccent` + `lower` veya normalize edilmiş arama sütunu.
  - `get_by_code` / `get_by_email` büyük/küçük harf duyarsız; `code` ve `email` benzersiz (DB'de unique index).
  - `add` id atar ve kaydı döner; tarihler UTC (`timestamptz`).
  - Silme eklenirse cascade: standart → requirement/chunk/vektör/PDF; rapor → analizler + dosya.
  - SQL'de `LIKE` aramasında `%` ve `_` kaçışı yapılır.
- **Seed:** Demo modu için `seed.py`'deki veriler DB'de de oluşturulabilmeli (geliştirme ortamı).

### 5.2 Sudenur — Madde bazlı parçalama + hibrit arama
- **Arayüz:** `SearchService` → `name`, `supports(mode)`, `search(...)`, `index_document(...)`.
- **Yer:** `src/infrastructure/search/` altında yeni modül (ör. `hybrid_search.py`). `mock_search.py` kalır.
- **Seçim:** `init_app_state()` içinde `SEARCH_PROVIDER` değerine göre (şu an `mock` dışı değer `RuntimeError` veriyor — oraya kendi dalını ekle).
- **Sözleşme gereği dönen `Source` alanları:** `chunk_id`, `standard_id`, `standard_code`, `snippet`, `score` (0–1), `requirement_id`, `section` (ör. `"Method 514.8"`), `page`. Sonuçlar skora göre **azalan** sırada, en fazla `top_k`.
- `search`'e gelen `standard_ids` zaten filtrelenmiştir (sadece `INDEXED` standartlar); boş/olmayan id ayıklaması servisin işi.
- `supports(mode)` `False` dönerse servis `semantic`'e düşer; desteklemediğin modu `True` deme.
- `index_document` hata durumunda **exception fırlatır** (servis bunu `FAILED`'a çevirir); `IndexResult(page_count, chunk_count, requirement_count)` döner. Uzun sürebilir, arka planda çağrılır.
- Ağır nesneler (embedding modeli, vektör istemcisi) `__init__`'te bir kez yüklenir; `init_app_state` bir kez çağırır.

### 5.3 Taha — Kayıt/giriş, JWT
- **Yer:** `src/core/security.py` (parola özeti, token üret/çöz), `src/application/services/auth_service.py`, `src/core/deps.py → get_current_user`.
- **Bugün:** stub token (`stub-access.<id>.<imza>`), `hashlib` tabanlı parola özeti. `AUTH_ENABLED=false` iken demo kullanıcı.
- **Yapılacak:** gerçek JWT (access 60 dk, refresh 7 gün), bcrypt/argon2 özet, `JWT_SECRET` ayarı (`config.py` + `.env.example`). Gerekli kütüphaneler PR'da gerekçeyle (Kural 7).
- **Değişmeyecekler:** `get_current_user` imzası ve davranışı (token yok/geçersiz → `UnauthorizedError` 401, rol yetersiz → `require_admin` 403). Router'lar ona dokunmadan çalışmaya devam etmeli.
- **Birleştirme (sözleşme değişikliği, §12):** `/auth/*` → `/api/v1/auth/*`, `TokenResponse.user` ve `UserOut.role` eklenir (sözleşme §3 hedef şekli). Yeni alan eklemek kırıcı değil; yol değişikliği kırıcı → bir süre eski yol `deprecated=True` ile tutulur.

### 5.4 Gemini istemcisi (LLM) — kim alırsa
- **Arayüz:** `LLMClient` → `model_name`, `answer(question, sources)`, `analyze(query, report_text, sources)`.
- **Yer:** `src/infrastructure/llm/gemini.py` (ör.). Seçim: `deps.py → _build_llm()` (`LLM_PROVIDER == "gemini"`).
- **Kurallar:**
  - Her türlü sağlayıcı hatasında (anahtar yok, kota, ağ, zaman aşımı) **`LLMError` fırlat**. Servis bunu sohbette `LLM_UNAVAILABLE` (200, kaynaklar dolu), analizde `503` (kayıt yok) yapar. Ham bağlam metnini cevap diye döndürme.
  - `model_name` gerçekten çağrılan model adı olmalı (`GEMINI_MODEL`); kayıtlara bu yazılır.
  - Analiz cevabı JSON istenir (`response_mime_type="application/json"`), Pydantic ile doğrulanır: `verdict` enum, `confidence` 0–1. Geçersizse 1 kez yeniden dene, yine olmazsa `INSUFFICIENT` + açıklama.
  - Prompt: "yalnızca verilen kaynaklara dayan, kaynak göster (standart, madde, sayfa)". Rapor metninin ilk N karakterini değil, sorguyla en ilgili rapor parçalarını gönder (sözleşme §6).
  - Anahtar `.env`'den (`GEMINI_API_KEY`); koda/log'a yazılmaz.

### 5.5 Onur — Standart PDF'leri, web arayüzü
- `POST /api/v1/standards/{id}/document` ile PDF yüklenir (ADMIN, `202`, polling `index-status`).
- `FileStorage.count_pages` şu an basit tahmin → gerçek PDF okuyucu (`TODO(Onur)` `local_storage.py`). Yüklenen dosya adı diske **asla** kullanılmaz (`uuid4().hex + ".pdf"`), `%PDF` imzası ve `MAX_UPLOAD_MB` kontrolü korunur.
- Web arayüzü yeni yollara geçer: eski → yeni eşleme `docs/REPO_ANALYSIS.md` §5. `POST /chat/ask` cevabında `answer` `null` olabilir → `status` alanına bak.
- DO-178C telifli: repoya PDF koyma.

### 5.6 Şeyma, Ammar — Mobil
Backend kodu yazmıyorsanız: Swagger (`/docs`) + `docs/API_CONTRACT.md` §7 yeterli. Enum/etiketleri uygulamaya gömmeyin, `GET /api/v1/meta/enums`'tan alın. Eksik/yanlış bir şey görürseniz koda değil, sözleşmeye issue/PR açın.

---

## 6. Endpoint ekleme / değiştirme adımları

Önce `docs/API_CONTRACT.md`'de endpoint'in satırı ve şeması var mı bak. Yoksa önce §12 (sözleşme değişikliği).

1. **Şema** — `src/application/schemas/<alan>.py`
   - İstek: `XxxCreate` / `XxxRequest` (sınırlar burada: `Field(min_length=..., ge=..., le=...)`, `model_config` içinde `str_strip_whitespace=True` — parolalar hariç).
   - Cevap: `XxxOut`, `model_config = ConfigDict(from_attributes=True, json_schema_extra={"examples": [...]})`; her alanda `Field(description="Türkçe", examples=[...])`.
   - Liste: `Page[XxxOut]` + router'da `paging: Annotated[PageParams, Query()]` ve `to_page(...)`.
   - Enum'lar `src/domain/enums.py`'den; şemada yeniden tanımlanmaz. Hesaplanan alanlar `computed_field`.
2. **Servis** — `src/application/services/<alan>_service.py`: arayüzleri constructor'da alır; HTTP bilmez; `AppError` alt sınıfları fırlatır; sahiplik kontrolü burada (`NotFoundError`).
3. **Dependency** — `src/core/deps.py`: `get_<alan>_service(request)` → `request.app.state`'teki nesnelerden servis kurar.
4. **Router** — `src/api/v1/<alan>.py` (gerçek örnek: `src/api/v1/standards.py`):
   ```python
   router = APIRouter(prefix="/standards", tags=["Standards"], dependencies=[Depends(get_current_user)])
   Service = Annotated[StandardsService, Depends(get_standards_service)]

   @router.get(
       "/{standard_id}",
       response_model=StandardOut,
       status_code=200,
       summary="Standart detayı",
       description="Tek bir standardın bilgilerini ve indeksleme özetini döner.",
       responses=errors({404: "Standart bulunamadı (NOT_FOUND)."}, auth=True),
   )
   def get_standard(standard_id: int, svc: Service) -> StandardOut:
       return StandardOut.model_validate(svc.get(standard_id))
   ```
   Zorunlu: `response_model`, `status_code`, `summary`, Türkçe `description`, `tags`, `responses=errors(...)`.
   Router fonksiyonu ≤ 15 satır. ADMIN uçları: `dependencies=[Depends(require_admin)]`.
5. **Kayıt** — yeni router dosyasıysa `src/api/v1/__init__.py`'ye ekle.
6. **Test** — §10. Yeni endpoint sözleşmeye girdiyse `tests/api/test_contract_coverage.py` listesini güncelle.
7. **Kontrol** — `pytest -q` yeşil; Swagger'da endpoint şemalı ve örnekli görünüyor.

---

## 7. API kuralları (sözleşme özeti)

| Konu | Kural |
|---|---|
| Taban yol | `/api/v1` (istisna: `/`, `/health`; auth şimdilik `/auth/*`) |
| Format | JSON, UTF-8. Dosya yükleme `multipart/form-data` |
| İsimler | Kod, alan, endpoint adları İngilizce `snake_case`; kullanıcıya dönen mesajlar Türkçe |
| Tarih | ISO 8601 UTC, `datetime.now(timezone.utc)` (`utc_now()`); `datetime.utcnow()` kullanma |
| ID | integer |
| Enum | Büyük harf string (`SearchMode` hariç: `semantic`/`keyword`/`hybrid`) |
| Sayfalama | `?page=1&page_size=20` (max 100) → `{items, total, page, page_size}` |
| Uzun iş | `202` + durum; istemci yoklar |
| Auth | `Authorization: Bearer <token>`; `/`, `/health`, `/meta/enums`, register/login/refresh hariç hepsi korumalı |
| Sahiplik | Rapor/sohbet/analiz sahibine özel; başkasınınki `404` |
| Metin | Baş/son boşluk kırpılır → yalnız boşluk = boş (`422`); parolalar kırpılmaz |
| `standard_ids` | Boş = tüm standartlar; olmayan/indekslenmemiş id'ler hata vermeden atlanır |

**Hata formatı (422 dahil hepsi):**
```json
{ "error": { "code": "NOT_FOUND", "message": "Standart bulunamadı: id=7", "details": null } }
```

| Durum | `code` | Servisten fırlatılan |
|---|---|---|
| 400 | `BAD_REQUEST` | `BadRequestError` |
| 401 | `UNAUTHORIZED` | `UnauthorizedError` |
| 403 | `FORBIDDEN` | `ForbiddenError` |
| 404 | `NOT_FOUND` | `NotFoundError` |
| 405 | `METHOD_NOT_ALLOWED` | (framework) |
| 409 | `CONFLICT` | `ConflictError` |
| 413 | `PAYLOAD_TOO_LARGE` | `PayloadTooLargeError` |
| 415 | `UNSUPPORTED_FILE` | `UnsupportedFileError` |
| 422 | `VALIDATION_ERROR` | (şema; otomatik) |
| 500 | `INTERNAL_ERROR` | (beklenmeyen exception; detay sadece log'a) |
| 503 | `LLM_UNAVAILABLE` | `LLMUnavailableError` |

Hepsi `src/core/errors.py`'de. Yeni hata kodu gerekiyorsa önce sözleşmeye eklenir.
Mesajlar Türkçe ve kullanıcıya gösterilebilir olmalı; içinde dosya yolu, SQL, stack trace, anahtar olmaz.

---

## 8. Kod standartları

- Python 3.14, tam type hint. Pydantic v2 (`model_validate`, `ConfigDict`), FastAPI `Annotated[...]` stili.
- Log: `loguru` (`from loguru import logger`). `print` yok. Log'a parola, token, API anahtarı yazılmaz.
- Docstring: her servis/arayüz/implementasyon için "ne işe yarar, gerçeğini kim takar" (Türkçe, kısa).
- `TODO(İsim): ...` formatı; isimsiz TODO bırakma.
- Kullanılmayan import/bağımlılık bırakma. İlgisiz dosyayı yeniden biçimlendirme (diff'i şişirir, review zorlaşır).
- Türkçe metinlerde Kiril/benzer görünen karakter olmasın (eski repoda vardı).
- Mock'lar deterministik (aynı girdi → aynı çıktı); mock LLM cevapları `[DEMO]` ile başlar.

---

## 9. Güvenlik

- Dosya: ad diske kullanılmaz (`uuid4().hex + ".pdf"`), uzantı + `%PDF` imzası + `MAX_UPLOAD_MB`, parça parça okuma. Önce kontrol (kayıt var mı, durum uygun mu), sonra yazma; hata olursa yarım dosya silinir.
- Gizli bilgiler `.env`'de; `.env` git'e girmez (`.gitignore`). Örnek değerler `.env.example`'da (gizli değer olmadan).
- 500 cevabında iç ayrıntı yok; ayrıntı log'a.
- Yetki: ADMIN uçları `require_admin`; sahiplik kontrolü servislerde.
- SQL'de parametreli sorgu (string birleştirme yok); `LIKE` kaçışı.
- CORS üretimde daraltılır (`CORS_ORIGINS`).

---

## 10. Test kuralları

- Çalıştırma: `.venv/Scripts/python -m pytest -q` — PR öncesi **tamamı yeşil** olmalı.
- Yapı: `tests/conftest.py` (fixture'lar), `tests/api/helpers.py` (yardımcılar), `tests/api/test_*.py`.
- Hazır fixture'lar: `client` (her test yeni `create_app()` + temiz bellek), `client_no_raise` (500 testleri),
  `make_client(**env)` (ör. `make_client(AUTH_ENABLED="true")`), `pdf_bytes`, `fake_pdf`, `storage_dir`.
- Yardımcılar: `assert_error_shape(resp, status, code)`, `assert_utc(value)`, `assert_source(src)`,
  `act_as(app, user)` (başka kullanıcı/rol), `pdf_upload(...)`, `stored_files(dir)`.
- Her yeni/değişen endpoint için: **mutlu yol** + **en az bir hata yolu** (404/409/415/422) + hata formatı.
- Gerçek implementasyon (DB, hibrit arama, Gemini) için: arayüz sözleşmesini test eden testler; ağ/anahtar gerektiren testler varsayılan çalıştırmada atlanmalı (işaretli, ör. `@pytest.mark.integration`) — **mock modda tüm suite internet ve anahtar olmadan geçmeli**.
- `tests/api/test_contract_coverage.py`: sözleşmedeki endpoint listesiyle kodun birebir aynı olduğunu sınar. Sözleşme değişmeden bu listeyi değiştirme.
- Yasak: test silmek, beklentiyi gevşetmek, `skip`/`xfail` ile kırmızıyı gizlemek. Bilinen bir hata için `xfail(strict=True)` + PR açıklamasında gerekçe.

---

## 11. Git ve PR süreci

### 11.1 Dallar
- `main` korumalı: doğrudan push yok; her değişiklik PR ile ve **2 onayla** birleşir.
- Hassas dosyalara (sözleşme, arayüzler, `requirements.txt`, `.github/`, bu rehber, `CLAUDE.md`/`AGENTS.md`) dokunan PR'larda onaylardan biri `.github/CODEOWNERS`'taki sahiplerden olmalıdır.
- PR açan kişi kendi PR'ını onaylayamaz. Onaydan sonra yeni commit gelirse onaylar sıfırlanır ve yeniden onay gerekir.
- Dal adı: `<isim>/<kısa-konu>` → `doruk/postgres-repositories`, `sudenur/hybrid-search`, `taha/jwt-auth`.
- Dalını sık sık `main`'den güncelle (`git pull --rebase origin main` veya merge); çakışmaları kendi dalında çöz.

### 11.2 Commit mesajı (Conventional Commits)
`feat(api): ...`, `fix(search): ...`, `test(api): ...`, `docs: ...`, `chore: ...`, `refactor(core): ...`
Açıklama Türkçe, kısa ve ne yaptığını söyleyen. Bir commit = bir anlamlı değişiklik.

### 11.3 PR açmadan önce kontrol listesi
PR açıklamasına bu listeyi kopyala ve işaretle:
```markdown
## Ne yaptım?
<2-4 madde>

## Takma noktası / etkilenen yer
<ör. SearchService → src/infrastructure/search/hybrid_search.py, deps.py'de SEARCH_PROVIDER=hybrid>

## Kontrol listesi
- [ ] `pytest -q` yerelde tamamen yeşil (sonucu yapıştır: `X passed`)
- [ ] Sözleşme (API_CONTRACT.md) değişmedi / değiştiyse önce sözleşme güncellendi ve duyuru metni aşağıda
- [ ] `src/domain/interfaces.py` imzaları değişmedi / değiştiyse gerekçe aşağıda
- [ ] Yeni bağımlılık yok / varsa `==` sürümle eklendi ve gerekçe aşağıda
- [ ] Yeni ayar varsa `config.py` + `.env.example` güncellendi; `.env` commit edilmedi
- [ ] Router'da iş mantığı yok; hatalar AppError ile; mesajlar Türkçe
- [ ] Yeni/değişen davranış için test eklendi (mutlu yol + hata yolu)
- [ ] Mock modda (`SEARCH_PROVIDER=mock`, `LLM_PROVIDER=mock`) uygulama hâlâ açılıyor ve tüm testler geçiyor
- [ ] Yapay zekâ ile üretilen kodu okudum ve anlıyorum

## Sözleşme değişikliği duyurusu (varsa)
```
- PR küçük tut: bir PR = bir konu. İlgisiz düzenlemeleri ayrı PR'a al.
- Review: herhangi 2 ekip üyesi. Değişiklikten etkilenen kişiyi (ör. arama değişikliğinde Sudenur, sözleşme değişikliğinde Şeyma/Ammar) PR'da reviewer olarak ekle.
- Onaylarken en az şunlara bak: kontrol listesi dolu mu, `pytest` kontrolü yeşil mi, değişiklik sözleşmeyle ve §1'deki kurallarla uyumlu mu.

### 11.4 GitHub ayarları (repo yöneticisi bir kez yapar)
Settings → Branches → `main` için kural (Branch protection rule / Ruleset):
- **Require a pull request before merging** → **Required approvals: 2**
- **Dismiss stale pull request approvals when new commits are pushed**
- **Require review from Code Owners** (hassas dosyalarda CODEOWNERS onayı)
- **Require status checks to pass before merging** → `pytest` (GitHub Actions işi; ilk çalışmadan sonra listede görünür)
- **Do not allow bypassing the above settings** (kurallar yöneticiler dahil herkese uygulanır)
- CODEOWNERS'ta adı geçenlerin repoda **yazma (write)** yetkisi olmalı; aksi halde GitHub onları sahip saymaz.

---

## 12. Sözleşme (API) değişikliği süreci

1. Değişikliği ve gerekçesini PR açıklamasında yaz; **kırıcı mı** belirt.
   - **Kırıcı:** alan silme/yeniden adlandırma, tip değişikliği, yol/metot değişikliği, zorunlu alan ekleme, enum değeri silme, status kodu değişikliği.
   - **Kırıcı değil:** opsiyonel alan ekleme, yeni endpoint, yeni enum değeri (mobil bilinmeyen değeri tolere etmeli), yeni hata kodu.
2. Önce `docs/API_CONTRACT.md` güncellenir, sonra kod, sonra `test_contract_coverage.py` listesi, sonra testler.
3. Kırıcı değişiklikte eski hali bir süre korunur (eski yol `deprecated=True`), mobil geçince kaldırılır.
4. PR açıklamasına duyuru metni:
   ```
   API değişikliği (v1) — <tarih>
   Ne değişti: <endpoint> — <alan/davranış>
   Kimi etkiler: <mobil / web / Taha / ...>
   Yapmanız gereken: <tek cümle>
   Kırıcı mı: Evet/Hayır
   ```

---

## 13. Yapılmayacaklar (eski repodan dersler)

| Yapma | Yerine |
|---|---|
| Router'da prompt, LLM çağrısı, iş mantığı | Servis + `LLMClient` |
| Her istekte yeni ChromaDB/embedding/Gemini istemcisi | Lifespan'de bir kez, `app.state` |
| `except Exception: raise HTTPException(500, detail=str(e))` | `AppError` alt sınıfı; beklenmeyen hata global handler'a |
| Kullanıcının dosya adını diske yazmak | `uuid4().hex + ".pdf"` |
| Hata durumunu yazıp sonra rollback ile kaybetmek | Arka planda kendi oturumunda `FAILED` + `error_message` commit |
| LLM yokken ham bağlamı `answer` diye döndürmek | `status: LLM_UNAVAILABLE`, `answer: null` |
| Kaydedilen model adı ≠ çağrılan model | `model_name` = gerçekte çağrılan |
| Geçersiz enum sorgu parametresi → 500 | Parametre tipi enum → otomatik 422 |
| Sahte değer uydurmak (ör. `publication_year=2020`) | Alan opsiyonel/`null` |
| `datetime.utcnow()`, `@app.on_event("startup")`, `load_dotenv()` her istekte | `datetime.now(timezone.utc)`, lifespan, `get_settings()` |
| `response_model`'siz endpoint | Her endpoint'te şema (Swagger mobilin dokümanı) |

Ayrıntı: `docs/REPO_ANALYSIS.md` (sadece referans).

---

## 14. Sık sorulanlar

**Mock'u silip gerçeğini mi koyuyorum?** Hayır. Mock kalır (testler ve demo onu kullanır). Gerçeğini yanına ekler, `deps.py`'de ayarla seçersin.

**Arayüzde ihtiyacım olan bir metot yok.** PR'da öner: yeni metot eklemek diğer implementasyonları da (mock dahil) etkiler; mock'a da aynı metodu ekle ki testler geçsin.

**Swagger'da yeni alanım görünmüyor.** Alan şemada (`src/application/schemas/`) yoksa görünmez; entity'ye eklemek yetmez. Sözleşmede yoksa önce sözleşme.

**Testler bende geçiyor, CI'da/arkadaşımda geçmiyor.** `.env`'in testleri etkilememesi gerekir (`conftest.py` ayarları sabitler); internet/anahtar gerektiren test varsayılan suite'e girmemeli.

**Bir kararı değiştirmek istiyorum (ör. 404 yerine 403).** Bu sözleşme değişikliğidir → §12.

---

## 15. Karar kaydı (neden böyle?)

| Karar | Gerekçe |
|---|---|
| `/api/v1` sürümleme | Mobil uygulamalar zorla güncellenemez; kırıcı değişiklik `v2` ile yapılır |
| Tek tip hata formatı | Mobil tek bir hata modeli yazar; iç bilgi sızmaz |
| Protocol arayüzler + `deps.py` | Ekip paralel çalışır; mock ↔ gerçek geçişi tek yerden |
| Bellek-içi mock + seed | Mobil ekip DB/arama/LLM beklemeden uçtan uca çalışır |
| `202` + polling | Büyük PDF'te zaman aşımı ve donma olmaz |
| Başkasının kaydı `404` | Kaydın varlığı sızdırılmaz |
| Sınırlar şemada (`top_k` ≤ 20, `page_size` ≤ 100) | Hatalı istek servise ulaşmadan 422; sınırlar Swagger'da görünür; `/meta/enums` aynı sabitleri döner |
| Auth şimdilik `/auth/*` | Taha'nın modülünün mevcut hali; birleştirmede `/api/v1/auth/*` |
