> **Not (yeni proje):** Bu doküman eski repoyu (`onurcansari/aerospace-compliance-platform`) analiz eder.
> `aerospace-mobile-api` sıfırdan yazıldığı için buradaki düzeltmeler doğrudan uygulanmaz; **aynı hataları
> tekrarlamamak için referans** olarak okunur (ör. H3: hata durumunu commit etmeden rollback, H4: dosya adını diske yazmak).

# Mevcut Repo Analizi — API İskeleti Açısından

Kaynak: `github.com/onurcansari/aerospace-compliance-platform` (son commit `51750b2`).
Kapsam: API katmanı ve ona doğrudan bağlı servis/altyapı kodu. Satır numaraları o commit'e göredir.

## 1. API ile ilgili dosyalar

| Dosya | Satır | Rolü | Durum |
|---|---|---|---|
| `main.py` | 54 | FastAPI app, CORS, router kaydı, startup | Yeniden yazılacak (lifespan, handler'lar, v1) |
| `src/api/routes/standards_router.py` | 357 | 8 standart endpoint'i + RAG sorgusu | Bölünecek: `standards.py`, `chat.py`, `search.py` |
| `src/api/routes/reports_router.py` | 127 | 4 rapor endpoint'i | `reports.py`, `analyses.py` |
| `src/application/services/standards_service.py` | 116 | Standart CRUD + PDF indeksleme | Korunacak, düzeltilecek |
| `src/application/services/compliance_service.py` | 276 | Rapor yükleme, analiz, Gemini | Bölünecek: `report_service`, `analysis_service`, `LLMClient` |
| `src/application/dtos/__init__.py` | 0 | Boş | → `src/application/schemas/` |
| `src/infrastructure/database/connection.py` | 56 | Engine, session, `get_db` | Config'e bağlanacak |
| `src/infrastructure/models/orm_models.py` | 91 | 4 tablo | Doruk genişletir; iskelet için alan eklemeleri var |
| `src/infrastructure/repositories/repositories.py` | 373 | 4 repository | Korunacak, küçük düzeltmeler |
| `src/rag/*` | 303 | PDF çıkarma, chunking, ChromaDB | Sudenur'un alanı; iskelet adaptörle sarar |
| `ui.html` | 1047 | Web arayüzü, `API` sabiti satır 503 | Onur yolları v1'e çevirir (bkz. §5) |
| `tests/` | 25 test | entity, chunker, repository | **API testi yok** |

## 2. Mevcut endpoint envanteri (14)

| Metot | Yol | Sorun |
|---|---|---|
| GET | `/` | – |
| GET | `/health` | DB/arama durumunu kontrol etmiyor |
| GET | `/api/standards/` | Geçersiz `status` → 500; sayfalama yok |
| POST | `/api/standards/` | Kod tekrarı 400 dönüyor (409 olmalı) |
| POST | `/api/standards/query` | Tüm iş mantığı router'da; `response_model` yok; LLM yoksa ham context'i `answer` diye dönüyor |
| POST | `/api/standards/bulk-index` | Private `service._repo` kullanımı; sahte `publication_year=2020`; senkron, timeout riski |
| GET | `/api/standards/search/{query}` | Arama path parametresinde (boşluk/özel karakter sorunlu) |
| GET | `/api/standards/{id}` | – |
| DELETE | `/api/standards/{id}` | Vektörleri ve PDF'i silmiyor (yetim veri) |
| POST | `/api/standards/{id}/index-pdf` | Standart yoksa 404 yerine 500; dosyayı standart kontrolünden önce yazıyor; senkron |
| GET | `/api/reports/` | Geçersiz `status` → 500 |
| POST | `/api/reports/upload` | Dosya adı güvenliği, hata durumunda rollback sorunu (bkz. H3) |
| POST | `/api/reports/{id}/analyze` | **Her zaman 500** (bkz. H1) |
| GET | `/api/reports/{id}/summary` | `response_model` yok |

## 3. Eksik endpoint'ler (mobil ve bugünkü görevler için)
Auth (4), standart güncelleme (PATCH), indeksleme durumu, PDF indirme (standart + rapor), requirement
listeleme/detay, ham arama, sohbet geçmişi (3), rapor detay/silme, analiz geçmişi, analiz detay, enum metadata.
Tam liste: `API_CONTRACT.md` §1 — toplam 32 endpoint.

## 4. Hatalar ve düzeltmeler

Önem: 🔴 Kritik (çalışmıyor/veri kaybı/güvenlik) · 🟠 Yüksek · 🟡 Orta · ⚪ Düşük

| # | Önem | Yer | Sorun | Düzeltme |
|---|---|---|---|---|
| H1 | 🔴 | `compliance_service.py:151,155` | `saved_log` tanımsız → `NameError`. Analiz yapılıp DB'ye yazılıyor ama istemciye **her zaman 500** dönüyor | `AnalysisRepository.save()` ile kaydet, dönen entity'yi kullan |
| H2 | 🔴 | `compliance_service.py:122` | Analiz logu ayrı `SessionLocal()` ile, repository atlanarak yazılıyor; transaction bütünlüğü yok; hata olursa session kapanmıyor | Request session + repository; ayrı session sadece arka plan görevlerinde |
| H3 | 🔴 | `reports_router.py:92` + `connection.py:get_db` | PDF okunamazsa servis `FAILED` yazıyor, router `HTTPException` fırlatıyor, `get_db` **rollback** yapıyor → `FAILED` durumu da rapor kaydı da kayboluyor; dosya diskte yetim kalıyor | Metin çıkarma arka planda, kendi session'ında; hata durumu commit edilir; istemciye 202 |
| H4 | 🔴 | `reports_router.py:70`, `standards_router.py:242,340` | Dosya adı doğrudan yol olarak kullanılıyor → aynı adlı dosyanın üzerine yazma, `../` ile path traversal; boyut sınırı yok; sadece uzantı kontrolü | `uuid4().hex + ".pdf"`, `%PDF` imza kontrolü, `MAX_UPLOAD_MB`, chunk'lı yazma |
| H5 | 🔴 | genel | Kimlik doğrulama yok; herkes her şeyi silebilir | `get_current_user` + rol kontrolü (Taha) |
| H6 | 🟠 | `requirements.txt` | `google-genai` yok → Gemini çağrısı ImportError, sessizce demo moda düşüyor. `openai`, `sentence-transformers`, `alembic` kullanılmıyor (ağır bağımlılık) | `google-genai` ekle, kullanılmayanları çıkar (alembic → Doruk karar verir) |
| H7 | 🟠 | `standards_router.py:152`, `compliance_service.py:35` | Gemini anahtarı `OPENAI_API_KEY` adıyla okunuyor; `load_dotenv()` her istekte | `pydantic-settings` ile `GEMINI_API_KEY`, tek seferlik `Settings` |
| H8 | 🟠 | `standards_router.py:178`, `compliance_service.py:130,228`, `orm_models.py` | Çağrılan model `gemini-3-flash-preview`, kaydedilen `gemini-2.5-flash`, ORM varsayılanı `gpt-4o` → denetim izi yanlış | Model adı config'den (`GEMINI_MODEL`), kaydedilen = çağrılan |
| H9 | 🟠 | `standards_service.py:31`, `compliance_service.py:29`, `standards_router.py:129` | Her istekte yeni `VectorStore` (ChromaDB client + embedding modeli) → yavaş, bellek | Lifespan'de tek instance, dependency ile enjekte |
| H10 | 🟠 | `standards_router.py:115-200` | `/query` iş mantığı, LLM çağrısı, prompt router içinde (mimariyi ihlal) | `ChatService` + `LLMClient` |
| H11 | 🟠 | `index-pdf`, `bulk-index`, `upload` | PDF işleme senkron; 1000 sayfalık standart dakikalar sürer → mobilde timeout | `BackgroundTasks` + `index_status` + durum endpoint'i |
| H12 | 🟠 | `orm_models.py:67` | `UserReportModel.analysis_logs` ilişkisinde cascade yok, FK `nullable=False` → rapor silinince SQLAlchemy FK'yı NULL yapmaya çalışır → IntegrityError (DELETE eklenince patlar) | `cascade="all, delete-orphan"`, `passive_deletes=True` |
| H13 | 🟠 | `standards_service.py:65`, `compliance_service.py:181` | Geçersiz `status` sorgu parametresi → yakalanmayan `ValueError` → 500 | Query parametresi enum tipinde → FastAPI 422 |
| H14 | 🟠 | birçok `except Exception` | `detail=str(e)` → iç hata mesajları istemciye sızıyor; standart yok hatası 500 dönüyor (`standards_router.py:357`) | `AppError` hiyerarşisi + global handler |
| H15 | 🟡 | `standards_router.py` (4 yerde) | `StandardResponse(...)` alan alan 4 kez kopyalanmış | `model_config = ConfigDict(from_attributes=True)` + `model_validate` |
| H16 | 🟡 | `/query`, `/analyze`, `/summary`, `/upload`, `/bulk-index`, `/index-pdf` | `response_model` yok → Swagger'da şema görünmüyor, mobil ekip formatı bilmiyor | Hepsine Pydantic cevap şeması |
| H17 | 🟡 | `standards_service.py:93-97` | `index_pdf` hem `save()` hem `mark_as_indexed()` çağırıyor (gereksiz); hata durumunda `is_indexed` false kalıyor ama hata kaydı yok | `index_status` + `error_message` alanları |
| H18 | 🟡 | `standards_service.delete_standard` | Chroma vektörleri ve PDF silinmiyor | Servis: vektör sil → dosya sil → kayıt sil |
| H19 | 🟡 | `user_report.py`, `compliance_service.py:60` | `COMPLETED` = "metin çıkarıldı" ama adı "analiz tamamlandı" gibi; `is_ready_for_analysis` `PENDING` bekliyor → çelişki | `UPLOADED/PROCESSING/READY/FAILED` |
| H20 | 🟡 | `compliance_service.py:109` | Raporun sadece ilk 3000 karakteri analiz ediliyor | Rapor parçalanır, sorguya en yakın parçalar seçilir |
| H21 | 🟡 | `compliance_service.py:_run_ai_analysis` | LLM JSON'u elle `split("```")` ile ayrıştırılıyor; doğrulama yok; `confidence` 1'den büyük gelirse entity `ValueError` | Gemini `response_mime_type="application/json"` + Pydantic doğrulama |
| H22 | 🟡 | `main.py:36` | `@app.on_event("startup")` deprecated | `lifespan` |
| H23 | 🟡 | `connection.py:8` | `DATABASE_URL` sabit SQLite; `PRAGMA` her bağlantıda (Postgres'te hata) | Config'den; PRAGMA sadece `sqlite` ise |
| H24 | 🟡 | `repositories.py:51` | `StandardRepository.save` güncellemede model `None` ise `AttributeError` | Kontrol + `NotFoundError` |
| H25 | ⚪ | entity'ler, ORM | `datetime.utcnow()` deprecated, timezone'suz | `datetime.now(timezone.utc)` |
| H26 | ⚪ | `standards_router.py` prompt, `standards_service.py`, `compliance_service.py` docstring | Türkçe metinlerde Kiril karakter (`Gorеv`, `isaretле`, `yukledigи`) | Temizle |
| H27 | ⚪ | `repositories.py:97` | `ilike` aramasında `%`/`_` kaçışı yok | `escape` |
| H28 | ⚪ | `COMMIT_CONVENTION.md` | Dosya boş | CLAUDE.md'deki Conventional Commits |
| H29 | ⚪ | `ComplianceVerdict.PARTIALLY_COMPLIANT = "PARTIAL"` | Enum adı ile değer farklı (kafa karıştırıcı ama API değeri doğru) | Değer korunur, sözleşmede değerler esas |
| H30 | ⚪ | `vector_store.py:search` | `if standard_id` → `0` id'de filtre kalkar; tek standart filtrelenebiliyor (çoklu yok) | `standard_ids: list[int]` + `$in` filtresi |

## 5. Web arayüzü (`ui.html`) yol eşlemesi — Onur için
| Satır | Eski | Yeni |
|---|---|---|
| 744 | `POST /api/reports/upload` | `POST /api/v1/reports` (202; `READY` olana kadar `GET /api/v1/reports/{id}` yokla) |
| 747 | `POST /api/reports/{id}/analyze` | `POST /api/v1/reports/{id}/analyses` (`standard_id` → `standard_ids: [id]`) |
| 753 | `POST /api/standards/query` | `POST /api/v1/chat/ask` (`answer` null olabilir → `status`'a bak) |
| 792, 826 | `GET /api/standards/` | `GET /api/v1/standards` → cevap artık `{items: [...]}` |
| 813 | `POST /api/standards/` | `POST /api/v1/standards` |
| 865 | `POST /api/standards/{id}/index-pdf` | `POST /api/v1/standards/{id}/document` (202 + polling) |
| 880 | `DELETE /api/standards/{id}` | `DELETE /api/v1/standards/{id}` |
| 956 | `POST /api/standards/bulk-index` | `POST /api/v1/standards/bulk-upload` |

## 6. Korunacak iyi taraflar
- Katmanlı yapı (domain/application/infrastructure/api) ve repository pattern — üzerine inşa edilecek.
- Entity doğrulamaları (`__post_init__`) ve iş kuralı property'leri (`verdict_label`, `is_high_confidence`).
- Chunker'daki global sayaç düzeltmesi, ChromaDB'de batch ekleme/silme.
- Mevcut 25 test — iskelet sonrası da geçmeye devam etmeli.
