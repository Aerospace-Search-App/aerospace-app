# Proje Genel Bakış — Aerospace Compliance Platform (Mobil)

## 1. Ne yapıyor, neden var?
Havacılık ve savunmada bir ürün (telsiz, radar, uçuş yazılımı...) teslim edilmeden önce standartlara uyduğu
**kanıtlanmak** zorunda. Standartlar çok büyük (MIL-STD-810H ≈ 1000 sayfa), İngilizce, çapraz referanslı;
gözden kaçan bir madde test tekrarı, gecikme veya sertifika reddi demek.

Platform iki şey sunar:
1. **Standart asistanı:** Mühendis doğal dille soru sorar ("Vibrasyon testi kaç saat sürmeli?"), sistem ilgili
   bölümleri bulur, Türkçe cevaplar ve **kaynak gösterir** (standart, madde, sayfa).
2. **Uyumluluk ön kontrolü:** Mühendis kendi raporunu yükler; sistem ilgili standart maddeleriyle karşılaştırıp
   `COMPLIANT / PARTIAL / NON_COMPLIANT / INSUFFICIENT` kararı, gerekçe ve güven skoru verir. Her analiz
   izlenebilirlik (traceability) için kaydedilir.

**Sınır:** Bu bir asistandır, resmi onay mercii değildir. Kaynak gösterimi bu yüzden zorunludur.

### Standartlar
| Kod | Konu | Not |
|---|---|---|
| MIL-STD-810H | Çevresel testler: sıcaklık, nem, titreşim, şok, tuz sisi... | Kamuya açık |
| MIL-STD-461G | Elektromanyetik uyumluluk (EMI/EMC) | Kamuya açık |
| DO-178C | Uçuş yazılımı sertifikasyonu | **Ücretli/telifli** — demo için repoya koyma |

## 2. Mimari

```
📱 Mobil (React Native/Flutter)   🌐 Web (ui.html)
              \                     /
               ▼   HTTPS + JWT     ▼
        ┌─────────── FastAPI /api/v1 ───────────┐
        │ api/v1 (router)  → ince katman         │
        │ application/services → iş mantığı      │
        │ domain → entity + arayüz (saf Python)  │
        │ infrastructure → DB, arama, LLM, dosya │
        └───────┬──────────────┬──────────┬──────┘
                ▼              ▼          ▼
         PostgreSQL/SQLite   Arama      Gemini
         (+ pgvector)       (Chroma →   (LLM)
                            hibrit)
```

### RAG akışı
```
HAZIRLIK (PDF yüklenince, arka planda)
PDF → PyMuPDF ile metin (sayfa no korunur) → parçalama (eski: 200 kelime/40 örtüşme; yeni: madde bazlı)
    → embedding → vektör deposu  (+ requirement kayıtları: section_id, başlık, sayfa)

SORU ANINDA
soru → arama (semantik + anahtar kelime = hibrit) → en iyi k parça
     → prompt (soru + parçalar + "sadece bunlara dayan, kaynak göster")
     → Gemini → cevap + kaynak listesi → kaydet (sohbet geçmişi)

ANALİZ
rapor (parçalanmış) + sorgu → ilgili standart parçaları + ilgili rapor parçaları
     → Gemini (JSON: verdict, reasoning, confidence) → doğrula → analysis_logs
```
- **Embedding:** Metni anlamını temsil eden sayı vektörüne çevirir; benzer anlam = yakın vektör.
- **Hibrit arama:** Vektör benzerliği (anlam) + full-text (tam terim: "Method 514.8", "RTCA") birleşimi.
  Standartlarda kod/madde numaraları çok olduğu için tek başına semantik arama yetmez.
- **Madde bazlı parçalama:** Sabit 200 kelime yerine standardın kendi bölüm yapısına (Method 514.8, 5.2.1...)
  göre bölmek → kaynak gösterimi "Sayfa 412" yerine "Method 514.8, Sayfa 412" olur.

### Katmanlar (Clean Architecture)
| Katman | Klasör | Görev | Kural |
|---|---|---|---|
| API | `src/api/v1` | HTTP ↔ şema | İş mantığı yok |
| Application | `src/application` | Servisler + şemalar | Arayüzlere bağımlı |
| Domain | `src/domain` | Entity, iş kuralları, arayüzler | Dış import yok |
| Infrastructure | `src/infrastructure`, `src/rag` | DB, arama, LLM, dosya | Arayüzleri uygular |
| Core | `src/core` | Config, hata, dependency | – |

## 3. Veri modeli (iskelet sonrası)
| Tablo | Önemli alanlar |
|---|---|
| `users` | id, email (unique), password_hash, full_name, role, created_at |
| `standards` | id, code (unique, büyük harf), title, standard_type, version, issuing_body, publication_year (nullable), status, index_status, index_error, page_count, chunk_count, pdf_key, indexed_at |
| `requirements` | id, standard_id → standards (CASCADE), section_id, title, requirement_text, category, page_number, chunk_id |
| `user_reports` | id, owner_id → users, title, original_filename, file_key, report_type, status, error_message, page_count, extracted_text, uploaded_at, processed_at |
| `analysis_logs` | id, report_id → user_reports (CASCADE), query, verdict, ai_reasoning, confidence_score, sources (JSON), llm_model_used, analysis_duration_ms, analyzed_at |
| `conversations` | id, owner_id → users, title, standard_ids (JSON), created_at, updated_at |
| `chat_messages` | id, conversation_id → conversations (CASCADE), question, answer (nullable), status, sources (JSON), model, duration_ms, created_at |
| (Doruk) `chunks` | pgvector'a geçişte: id, standard_id, requirement_id, text, page, embedding vector, tsv tsvector |

## 4. Ortam değişkenleri
| Değişken | Varsayılan | Açıklama |
|---|---|---|
| `APP_ENV` | `dev` | dev/test/prod |
| `DATABASE_URL` | `sqlite:///./dev.db` | Postgres: `postgresql+psycopg://app:app@localhost:5432/aerospace` |
| `SEARCH_BACKEND` | `mock` | `mock`, `chroma`, `pg_hybrid` |
| `CHROMA_DIR` | `./chroma_db` | |
| `LLM_PROVIDER` | `mock` | `mock`, `gemini` |
| `GEMINI_API_KEY` | – | Eski kodda yanlışlıkla `OPENAI_API_KEY` |
| `GEMINI_MODEL` | `gemini-2.5-flash` | Kaydedilen model adı da bu |
| `AUTH_ENABLED` | `false` | |
| `JWT_SECRET`, `JWT_EXPIRE_MINUTES`, `JWT_REFRESH_EXPIRE_DAYS` | –, 60, 7 | Taha |
| `STORAGE_DIR` | `./storage` | uuid adlı PDF'ler |
| `MAX_UPLOAD_MB` | `50` | |
| `CORS_ORIGINS` | `*` | prod'da daralt |

## 5. Ekip
| Kişi | Bugünkü görev |
|---|---|
| Kağan | API iskeleti (Swagger), sözleşme |
| Taha | Kayıt/giriş, JWT doğrulama |
| Doruk | PostgreSQL şeması, chunk yükleme ve arama sorgusu |
| Sudenur | Madde bazlı parçalama, hibrit arama, kaynaklı cevap |
| Onur | Standart PDF'leri toplama, web yükleme, sohbetin API'ye bağlanması |
| Şeyma, Ammar | Mobil iskelet, giriş/kayıt ve sohbet ekranları |

Repo, ekip üyesi Onurcan Sarı'nın önceki çalışmasına dayanır; mobil uygulama ve backend genişletmeleri
Mobil Uygulamalar dersi projesi kapsamında geliştirilmektedir.
