# API Sözleşmesi (v1)

> **Tek doğruluk kaynağı.** Mobil ekip, backend ekibi ve testler bu dosyaya göre çalışır.
> Değişiklik önce burada yapılır, sonra kodda. Kod ile bu dosya çelişirse bu dosya kazanır.
> Swagger: `http://<host>:8000/docs` · OpenAPI JSON: `/openapi.json`

## 0.1 Bu iterasyon (27 Ekim 2026 sunumu) — çekirdek set
Bu hafta 32 endpoint'in **20'lik çekirdeği** uygulanır; liste `docs/TASK_API_SKELETON.md`'dedir
(§1 tablosundaki #1–3, #4–7 auth, #8–10, #13, #15, #19–22, #24–26, #29). Kalanlar sonraki iterasyonda.
İki istisna:
- **Auth yolları `/auth/*`** (prefix'siz) ve şemaları Taha'nın mevcut modülüyle aynıdır (§3'teki kutu).
  Birleştirmede router tek satırla `/api/v1` altına alınacak ve `user` / `role` alanları eklenecek.
- Tüm servisler **mock / bellek-içi** çalışır (DB, ChromaDB, Gemini yok).

## 0. Genel kurallar

| Konu | Kural |
|---|---|
| Taban yol | `/api/v1` (sistem endpoint'leri hariç) |
| Format | JSON, UTF-8. Dosya yüklemeleri `multipart/form-data` |
| Auth | `Authorization: Bearer <access_token>`. Swagger'da **HTTPBearer** şeması ("Authorize" butonu) |
| Kimler auth ister | `auth/register`, `auth/login`, `auth/refresh`, `/`, `/health`, `/meta/enums` hariç **hepsi** (`AUTH_ENABLED=false` iken demo kullanıcı) |
| Rol | `ENGINEER` (varsayılan), `ADMIN`. 🔒A = sadece ADMIN |
| Tarih | ISO 8601 UTC, örn. `2026-10-26T09:30:00Z` |
| ID | integer (`conversation_id` dahil) |
| Sayfalama | `?page=1&page_size=20` (max 100) → `Page[T]` |
| Uzun işler | `202 Accepted` + durum alanı; istemci durum endpoint'ini yoklar (polling) |
| Metin alanları | İstekte baştaki/sondaki boşluk kırpılır, sonra uzunluk kontrol edilir → yalnız boşluk = boş (`422`). Parolalar kırpılmaz |
| Metin araması (`q`) | Büyük/küçük harf, Türkçe harf (İ/ı/I/i) ve aksan duyarsız: `TİTREŞİM`, `titreşim`, `titresim` aynı sonucu verir |
| `standard_ids` | Boş liste veya gönderilmezse tüm standartlar. Var olmayan / indekslenmemiş id'ler hata vermeden atlanır (hepsi elenirse sonuç boş) |

### Ortak şemalar
```jsonc
// Page[T]
{ "items": [T], "total": 42, "page": 1, "page_size": 20 }

// ErrorResponse — TÜM 4xx/5xx cevapları bu formatta (422 dahil)
{ "error": { "code": "NOT_FOUND", "message": "Standart bulunamadı: id=7", "details": null } }
```
Hata kodları: `VALIDATION_ERROR`(422) · `BAD_REQUEST`(400) · `UNAUTHORIZED`(401) · `FORBIDDEN`(403) ·
`NOT_FOUND`(404) · `METHOD_NOT_ALLOWED`(405) · `CONFLICT`(409) · `PAYLOAD_TOO_LARGE`(413) · `UNSUPPORTED_FILE`(415) ·
`LLM_UNAVAILABLE`(503) · `INTERNAL_ERROR`(500)
Yedek: listede karşılığı olmayan bir framework durum kodu gelirse `code: "HTTP_ERROR"` döner (HTTP durumu korunur; pratikte beklenmez).

### Enum'lar
| Enum | Değerler |
|---|---|
| `StandardType` | `MIL`, `CIVIL`, `INTL` |
| `StandardStatus` | `ACTIVE`, `SUPERSEDED`, `ARCHIVED` |
| `IndexStatus` | `NOT_INDEXED`, `PENDING`, `PROCESSING`, `INDEXED`, `FAILED` |
| `RequirementCategory` | `ENVIRONMENTAL`, `EMC`, `SOFTWARE`, `STRUCTURAL`, `SAFETY` |
| `ReportType` | `DESIGN`, `TEST`, `QUAL`, `COMPLIANCE` |
| `ReportStatus` | `UPLOADED`, `PROCESSING`, `READY`, `FAILED` |
| `ComplianceVerdict` | `COMPLIANT`, `PARTIAL`, `NON_COMPLIANT`, `INSUFFICIENT` |
| `SearchMode` | `semantic`, `keyword`, `hybrid` |
| `ChatStatus` | `ANSWERED`, `NO_RESULTS`, `LLM_UNAVAILABLE` |
| `UserRole` | `ENGINEER`, `ADMIN` |

> `ReportStatus` değişti: eskiden metin çıkarılınca `COMPLETED` deniyordu (yanıltıcı).
> Yeni: `UPLOADED → PROCESSING → READY` (analize hazır) / `FAILED`.

---

## 1. Endpoint listesi (tam liste — 32 endpoint)

| # | Metot | Yol | Auth | Durum | Sahip | Eski karşılığı |
|---|---|---|---|---|---|---|
| 1 | GET | `/` | – | 200 | Kağan | `GET /` |
| 2 | GET | `/health` | – | 200 | Kağan | `GET /health` |
| 3 | GET | `/api/v1/meta/enums` | – | 200 | Kağan | **YENİ** |
| 4 | POST | `/api/v1/auth/register` | – | 201 | Taha | **YENİ** |
| 5 | POST | `/api/v1/auth/login` | – | 200 | Taha | **YENİ** |
| 6 | POST | `/api/v1/auth/refresh` | – | 200 | Taha | **YENİ** |
| 7 | GET | `/api/v1/auth/me` | ✓ | 200 | Taha | **YENİ** |
| 8 | GET | `/api/v1/standards` | ✓ | 200 | Kağan/Doruk | `GET /api/standards/` + `GET /api/standards/search/{query}` |
| 9 | POST | `/api/v1/standards` | 🔒A | 201 | Kağan/Doruk | `POST /api/standards/` |
| 10 | GET | `/api/v1/standards/{standard_id}` | ✓ | 200 | Kağan/Doruk | `GET /api/standards/{id}` |
| 11 | PATCH | `/api/v1/standards/{standard_id}` | 🔒A | 200 | Kağan/Doruk | **YENİ** |
| 12 | DELETE | `/api/v1/standards/{standard_id}` | 🔒A | 204 | Kağan/Doruk | `DELETE /api/standards/{id}` |
| 13 | POST | `/api/v1/standards/{standard_id}/document` | 🔒A | 202 | Kağan/Sudenur | `POST /api/standards/{id}/index-pdf` |
| 14 | GET | `/api/v1/standards/{standard_id}/document` | ✓ | 200 (PDF) | Kağan | **YENİ** (mobil PDF görüntüleyici) |
| 15 | GET | `/api/v1/standards/{standard_id}/index-status` | ✓ | 200 | Kağan | **YENİ** |
| 16 | POST | `/api/v1/standards/bulk-upload` | 🔒A | 202 | Kağan/Onur | `POST /api/standards/bulk-index` |
| 17 | GET | `/api/v1/standards/{standard_id}/requirements` | ✓ | 200 | Sudenur | **YENİ** |
| 18 | GET | `/api/v1/requirements/{requirement_id}` | ✓ | 200 | Sudenur | **YENİ** |
| 19 | POST | `/api/v1/search` | ✓ | 200 | Sudenur | **YENİ** (ham arama, LLM'siz) |
| 20 | POST | `/api/v1/chat/ask` | ✓ | 200 | Kağan/Sudenur | `POST /api/standards/query` |
| 21 | GET | `/api/v1/chat/conversations` | ✓ | 200 | Kağan | **YENİ** |
| 22 | GET | `/api/v1/chat/conversations/{conversation_id}` | ✓ | 200 | Kağan | **YENİ** |
| 23 | DELETE | `/api/v1/chat/conversations/{conversation_id}` | ✓ | 204 | Kağan | **YENİ** |
| 24 | GET | `/api/v1/reports` | ✓ | 200 | Kağan | `GET /api/reports/` |
| 25 | POST | `/api/v1/reports` | ✓ | 202 | Kağan | `POST /api/reports/upload` |
| 26 | GET | `/api/v1/reports/{report_id}` | ✓ | 200 | Kağan | **YENİ** |
| 27 | DELETE | `/api/v1/reports/{report_id}` | ✓ | 204 | Kağan | **YENİ** (repo'da vardı, endpoint yoktu) |
| 28 | GET | `/api/v1/reports/{report_id}/file` | ✓ | 200 (PDF) | Kağan | **YENİ** |
| 29 | POST | `/api/v1/reports/{report_id}/analyses` | ✓ | 201 | Kağan | `POST /api/reports/{id}/analyze` |
| 30 | GET | `/api/v1/reports/{report_id}/analyses` | ✓ | 200 | Kağan | **YENİ** (analiz geçmişi) |
| 31 | GET | `/api/v1/reports/{report_id}/summary` | ✓ | 200 | Kağan | `GET /api/reports/{id}/summary` |
| 32 | GET | `/api/v1/analyses/{analysis_id}` | ✓ | 200 | Kağan | **YENİ** |

**Eski 14 endpoint'in hepsi karşılanıyor** (12 API + `/` + `/health`). Eski `GET /search/{query}`,
`GET /standards?q=` parametresine birleşti. Kullanıcı rapor/sohbet verisi kullanıcıya özeldir:
başkasının kaydına erişim → `404` (varlığını sızdırmamak için 403 değil).

---

## 2. Sistem

### 1 · `GET /`
`200` → `{ "app": "Aerospace Compliance Platform", "version": "1.1.0", "docs": "/docs", "api": "/api/v1" }`

### 2 · `GET /health`
`200` → `{ "status": "ok", "version": "1.1.0", "checks": { "database": "ok", "search": "mock", "llm": "mock" } }`
Bir bileşen çalışmıyorsa `status: "degraded"` ve ilgili check `"error"` (yine 200; mobil açılışta bunu okur).

### 3 · `GET /api/v1/meta/enums`
`200` → `{ "standard_types": ["MIL","CIVIL","INTL"], "standard_statuses": [...], "index_statuses": [...], "requirement_categories": [...], "report_types": [...], "report_statuses": [...], "verdicts": [{"value":"COMPLIANT","label_tr":"Uyumlu","label_en":"Compliant"}, ...], "search_modes": [...], "limits": {"max_upload_mb": 50, "max_top_k": 20, "max_page_size": 100} }`
Mobil dropdown'lar ve etiketler buradan beslenir; enum'lar uygulamaya gömülmez.

| `verdict` | `label_tr` | `label_en` |
|---|---|---|
| `COMPLIANT` | Uyumlu | Compliant |
| `PARTIAL` | Kısmen Uyumlu | Partially Compliant |
| `NON_COMPLIANT` | Uyumsuz | Non-Compliant |
| `INSUFFICIENT` | Yetersiz Bilgi | Insufficient Information |

---

## 3. Auth (Taha) — iskelette şema + stub

> **Bu hafta: Taha'nın şekli** (iskelet bunu birebir gösterir)
> | Metot | Yol | Başarı | Cevap |
> |---|---|---|---|
> | POST | `/auth/register` | 201 | `{ "id": 1, "email": "taha@test.com", "full_name": "Taha", "created_at": "..." }` |
> | POST | `/auth/login` | 200 | `{ "access_token": "eyJ...", "refresh_token": "eyJ...", "token_type": "bearer", "expires_in": 3600 }` |
> | POST | `/auth/refresh` | 200 | login ile aynı (yeni token çifti) |
> | GET | `/auth/me` | 200 | register cevabıyla aynı kullanıcı nesnesi |
> İstekler aşağıdakiyle aynı (`RegisterRequest`, `LoginRequest`, `RefreshRequest`). Access token 60 dk, refresh 7 gün.
> Hedef (aşağıdaki) şekilden farkı: yol prefix'i, `TokenResponse.user` ve `UserOut.role` yok.

```jsonc
// RegisterRequest
{ "email": "kagan@example.com", "password": "min8karakter", "full_name": "Kağan Bayrak" }
// LoginRequest
{ "email": "kagan@example.com", "password": "..." }
// RefreshRequest
{ "refresh_token": "..." }
// TokenResponse
{ "access_token": "eyJ...", "refresh_token": "eyJ...", "token_type": "bearer", "expires_in": 3600, "user": UserOut }
// UserOut
{ "id": 1, "email": "kagan@example.com", "full_name": "Kağan Bayrak", "role": "ENGINEER", "created_at": "..." }
```
| # | Endpoint | Gövde | Başarı | Hatalar |
|---|---|---|---|---|
| 4 | register | RegisterRequest | 201 `UserOut` | 409 email kayıtlı, 422 |
| 5 | login | LoginRequest (JSON) | 200 `TokenResponse` | 401 hatalı bilgi |
| 6 | refresh | RefreshRequest | 200 `TokenResponse` | 401 geçersiz/süresi dolmuş |
| 7 | me | – | 200 `UserOut` | 401 |

İskelet davranışı (`AUTH_ENABLED=false`): login/register sahte token döner, `get_current_user` demo
kullanıcıyı (`id=1, role=ADMIN`) döner. Taha sadece `auth_service.py` + `security.py`'yi doldurur.

---

## 4. Standartlar

```jsonc
// StandardOut
{
  "id": 1, "code": "MIL-STD-810H", "title": "Environmental Engineering Considerations and Laboratory Tests",
  "standard_type": "MIL", "version": "H", "issuing_body": "U.S. Department of Defense",
  "publication_year": 2019, "description": "...", "status": "ACTIVE",
  "index_status": "INDEXED", "is_indexed": true, "has_document": true,
  "page_count": 1089, "chunk_count": 5210, "requirement_count": 312,
  "indexed_at": "2026-10-26T09:30:00Z", "created_at": "...", "updated_at": "..."
}
// StandardCreate
{ "code": "MIL-STD-810H", "title": "...", "standard_type": "MIL", "version": "H",
  "issuing_body": "U.S. Department of Defense", "publication_year": 2019, "description": null }
// StandardUpdate — tüm alanlar opsiyonel (code hariç; code değişmez)
{ "title": "...", "version": "...", "status": "SUPERSEDED", "description": "..." }
// IndexStatusOut
{ "standard_id": 1, "index_status": "PROCESSING", "progress": 0.4, "page_count": 1089,
  "chunk_count": 0, "error_message": null, "started_at": "...", "finished_at": null }
```

| # | Endpoint | Girdi | Başarı | Hatalar |
|---|---|---|---|---|
| 8 | `GET /standards` | query: `q` (kod/başlıkta arama), `standard_type`, `status`, `index_status`, `page`, `page_size` | 200 `Page[StandardOut]` | 422 geçersiz enum |
| 9 | `POST /standards` | `StandardCreate` | 201 `StandardOut` | 409 kod mevcut (büyük/küçük harf duyarsız), 422 |
| 10 | `GET /standards/{id}` | – | 200 `StandardOut` | 404 |
| 11 | `PATCH /standards/{id}` | `StandardUpdate` | 200 `StandardOut` | 404, 422 |
| 12 | `DELETE /standards/{id}` | – | 204 | 404. **Vektörler + PDF dosyası + requirement'lar da silinir** |
| 13 | `POST /standards/{id}/document` | multipart `file` (PDF) | 202 `IndexStatusOut` (`PENDING`) | 404, 413, 415, 409 zaten `PENDING`/`PROCESSING` |
| 14 | `GET /standards/{id}/document` | – | 200 `application/pdf` (`FileResponse`) | 404 belge yok |
| 15 | `GET /standards/{id}/index-status` | – | 200 `IndexStatusOut` | 404 |
| 16 | `POST /standards/bulk-upload` | multipart `files[]` | 202 `BulkUploadOut` | 413, 422 |
| 17 | `GET /standards/{id}/requirements` | `category`, `q`, `page`, `page_size` | 200 `Page[RequirementOut]` | 404 |
| 18 | `GET /requirements/{id}` | – | 200 `RequirementOut` | 404 |

```jsonc
// BulkUploadOut
{ "total": 3, "accepted": 2, "rejected": 1,
  "items": [ { "filename": "MIL-STD-810H.pdf", "status": "ACCEPTED", "standard_id": 1, "code": "MIL-STD-810H", "created": false, "reason": null },
             { "filename": "notlar.docx", "status": "REJECTED", "standard_id": null, "code": null, "created": false, "reason": "UNSUPPORTED_FILE" } ] }
// RequirementOut
{ "id": 10, "standard_id": 1, "standard_code": "MIL-STD-810H", "section_id": "Method 514.8",
  "title": "Vibration", "requirement_text": "...", "category": "ENVIRONMENTAL", "page_number": 412 }
```
Bulk-upload kuralları: dosya adından kod türetilir (`MIL-STD-810H.pdf` → `MIL-STD-810H`); kod varsa mevcut
standarda bağlanır (`created:false`), yoksa `standard_type` = kodda `MIL` geçiyorsa `MIL` değilse `CIVIL`,
`version`/`issuing_body`/`publication_year` = `null`/`"UNKNOWN"` (sahte `2020` yazılmaz → bu alanlar şemada opsiyonel olur).

---

## 5. Arama ve Sohbet

```jsonc
// SourceOut — RAG'ın bulduğu her parça (search ve chat ortak)
{ "chunk_id": "std_1_chunk_0042", "standard_id": 1, "standard_code": "MIL-STD-810H",
  "requirement_id": 10, "section": "Method 514.8", "page": 412,
  "snippet": "The test item shall be ...", "score": 0.87 }
```

### 19 · `POST /search`
Gövde: `{ "query": "vibrasyon testi süresi", "standard_ids": [1], "top_k": 5, "mode": "hybrid" }`
(`query` 2–500 karakter; `standard_ids` boş liste veya gönderilmezse **tüm standartlarda** aranır;
`top_k` 1–20, varsayılan 5; `mode` varsayılan `hybrid`, desteklenmiyorsa servis `semantic`'e düşer)
`200` → `{ "query": "...", "mode": "hybrid", "results": [SourceOut], "duration_ms": 42 }`

### 20 · `POST /chat/ask`
Gövde: `{ "question": "Vibrasyon testi kaç saat sürmeli?", "standard_ids": [1], "conversation_id": null, "top_k": 5 }`
- `conversation_id: null` → yeni sohbet açılır; doluysa o sohbete eklenir (başkasınınsa 404).
- `question` 3–2000 karakter. `standard_ids` boş liste veya gönderilmezse tüm standartlar kullanılır. `top_k` 1–20, varsayılan 5.

`200` → 
```jsonc
{ "conversation_id": 5, "message_id": 31, "question": "...",
  "answer": "MIL-STD-810H Method 514.8'e göre ... (Sayfa 412)",
  "status": "ANSWERED", "sources": [SourceOut], "model": "gemini-2.5-flash", "duration_ms": 1830,
  "created_at": "..." }
```
- Arama sonuç bulamazsa: `status: "NO_RESULTS"`, `answer: null`, `sources: []` (yine 200).
- LLM hata verirse/anahtar yoksa: `status: "LLM_UNAVAILABLE"`, `answer: null`, `sources` dolu
  (mobil "kaynaklar bulundu ama cevap üretilemedi" gösterir). Eski kod burada ham context'i `answer`
  alanına basıyordu — artık yapılmaz.

### 21 · `GET /chat/conversations` → `Page[ConversationOut]`
`ConversationOut`: `{ "id": 5, "title": "Vibrasyon testi kaç saat...", "message_count": 4, "standard_ids": [1], "created_at": "...", "updated_at": "..." }`
(`title` = ilk sorunun ilk 60 karakteri)

### 22 · `GET /chat/conversations/{id}` → `ConversationDetailOut`
`ConversationOut` + `"messages": [ { "id": 31, "question": "...", "answer": "...", "status": "ANSWERED", "sources": [SourceOut], "created_at": "..." } ]`

### 23 · `DELETE /chat/conversations/{id}` → 204 (404 yoksa)

---

## 6. Raporlar ve Uyumluluk Analizi

```jsonc
// ReportOut
{ "id": 3, "title": "Telsiz Titreşim Test Raporu", "original_filename": "rapor.pdf",
  "report_type": "TEST", "status": "READY", "file_size_kb": 812.4, "page_count": 24,
  "analysis_count": 2, "error_message": null, "uploaded_at": "...", "processed_at": "..." }
// AnalysisCreate
{ "query": "Rapor vibrasyon gereksinimlerini karşılıyor mu?", "standard_ids": [1], "top_k": 5 }
// AnalysisOut
{ "id": 12, "report_id": 3, "query": "...", "verdict": "PARTIAL", "verdict_label": "Kısmen Uyumlu",
  "confidence": 0.78, "is_high_confidence": false, "reasoning": "...",
  "sources": [SourceOut], "model": "gemini-2.5-flash", "duration_ms": 2400, "created_at": "..." }
// ComplianceSummaryOut
{ "report_id": 3, "report_title": "...", "report_status": "READY", "total": 4,
  "compliant": 1, "partial": 2, "non_compliant": 1, "insufficient": 0,
  "compliance_rate": 0.25, "average_confidence": 0.74, "last_analyzed_at": "..." }
```

| # | Endpoint | Girdi | Başarı | Hatalar |
|---|---|---|---|---|
| 24 | `GET /reports` | `status`, `report_type`, `q` (başlık ve dosya adında arama), `page`, `page_size` | 200 `Page[ReportOut]` (sadece kendi raporları) | 422 |
| 25 | `POST /reports` | multipart: `file` (PDF, zorunlu), `title` (ops.), `report_type` (vars. `DESIGN`) | 202 `ReportOut` (`UPLOADED`/`PROCESSING`) | 413, 415, 422 |
| 26 | `GET /reports/{id}` | – | 200 `ReportOut` | 404 |
| 27 | `DELETE /reports/{id}` | – | 204 (analizler + dosya da silinir) | 404 |
| 28 | `GET /reports/{id}/file` | – | 200 `application/pdf` | 404 |
| 29 | `POST /reports/{id}/analyses` | `AnalysisCreate` | 201 `AnalysisOut` | 404, 409 rapor `READY` değil, 503 LLM yok (analiz kaydedilmez) |
| 30 | `GET /reports/{id}/analyses` | `page`, `page_size` | 200 `Page[AnalysisOut]` (yeniden eskiye) | 404 |
| 31 | `GET /reports/{id}/summary` | – | 200 `ComplianceSummaryOut` (analiz yoksa sayılar 0) | 404 |
| 32 | `GET /analyses/{id}` | – | 200 `AnalysisOut` | 404 |

Analiz notları:
- `AnalysisCreate`: `query` 3–2000 karakter; `standard_ids` boş liste veya gönderilmezse tüm standartlar; `top_k` 1–20, varsayılan 5.
- `verdict_label` ve `is_high_confidence` saklanmaz, hesaplanır: etiket `verdict`'ten (§2 etiket tablosu), `is_high_confidence` = `confidence ≥ 0.8`.
- `LLM_PROVIDER=mock` iken deterministik sahte sonuç döner (`INSUFFICIENT`, `confidence 0.5`, gerekçe `[DEMO]` ile başlar).
- Rapor metni uzunsa ilk 3000 karakter **değil**; rapor da parçalanır ve sorguyla en ilgili rapor parçaları
  (varsayılan 3 parça, ~6000 karakter sınırı) prompt'a girer.
- LLM cevabı Pydantic ile doğrulanır (`verdict` enum, `confidence` 0–1). Geçersizse 1 kez yeniden denenir,
  yine olmazsa `INSUFFICIENT` + açıklama.

---

## 7. Mobil için notlar
- Android emülatör → `http://10.0.2.2:8000`, gerçek cihaz → bilgisayarın LAN IP'si veya tünel (ngrok/cloudflared).
  Sunucu `--host 0.0.0.0` ile başlatılmalı. Base URL uygulamada config'den okunur.
- Yükleme sonrası polling: `GET /standards/{id}/index-status` veya `GET /reports/{id}` her 2 sn, `READY/INDEXED/FAILED` olunca dur.
- Kaynak kartına tıklanınca: `GET /standards/{standard_id}/document` ile PDF açılır ve `page`'e atlanır.
- Tip üretimi: `/openapi.json`'dan istemci kodu üretilebilir (openapi-typescript / openapi-generator).
