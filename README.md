# AeroStandart AI — Sivil Havacılık & Savunma Standart Asistanı

Kullanıcıların projelerine ilişkin bilmeleri gereken standartları **madde ve sayfa atfıyla** önüne getiren, RAG (Retrieval-Augmented Generation) tabanlı mobil asistan.

| Katman | Teknoloji |
|---|---|
| Mobil | React Native + **Expo SDK 58** (TypeScript, Expo Router) — Expo Go ile çalışır |
| Backend | Python **FastAPI** (Swagger: `/docs`), JWT kimlik doğrulama |
| Veritabanı | **PostgreSQL 16 + pgvector** (tam metin `tsvector` + vektör, tek tabloda) |
| LLM / Embedding | Google **Gemini** (`gemini-flash-latest`, `gemini-embedding-2`, 768 boyut) |
| PDF ayrıştırma | PyMuPDF — madde (clause) bazlı parçalama |
| Web yönetim paneli | `/admin` — PDF yükleme, indeksleme durumu, arama testi |

---

## Hızlı başlangıç (Windows)

**Gerekenler:** Docker Desktop, Node.js 20+ (LTS), telefonda **Expo Go** (mağazadaki güncel sürüm — SDK 58), ücretsiz bir Gemini API anahtarı ([aistudio.google.com/apikey](https://aistudio.google.com/apikey)).

```powershell
# 1) Backend: PostgreSQL + API (ilk çalıştırmada .env oluşturur, Gemini anahtarını sorar)
.\start-backend.ps1

# 2) Mobil uygulama: QR kodu Expo Go ile okutun
.\start-mobile.ps1
```

> PowerShell betik çalıştırmayı engellerse bir kez: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`
>
> Telefon bilgisayara ulaşamıyorsa (sunucu durumu kırmızı): yönetici PowerShell'de `.\allow-firewall.ps1` çalıştırın. Telefon ile bilgisayar **aynı Wi-Fi** ağında olmalı. Giriş ekranının altındaki "Sunucu…" satırına dokunarak adresi elle de girebilirsiniz.

İlk açılışta veritabanı boşsa kamuya açık standartlar **arka planda otomatik indirilir**, madde bazında ayrıştırılır ve indekslenir. İlerleme: `http://<bilgisayar-ip>:8000/admin`.

- Yönetim paneli girişi: `admin@aerostd.dev` / `Admin12345!` (`.env` → `ADMIN_EMAIL`, `ADMIN_PASSWORD`)
- Swagger: `http://<bilgisayar-ip>:8000/docs` → `/api/auth/login` ile token alın, **Authorize**'a yapıştırın.

### Manuel çalıştırma (Docker olmadan / macOS / Linux)

```bash
# PostgreSQL 16 + pgvector kurulu olmalı
cd backend && python -m venv .venv && . .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
export DATABASE_URL=postgresql://kullanici:parola@localhost:5432/aerostd GEMINI_API_KEY=...
uvicorn app.main:app --host 0.0.0.0 --port 8000

cd ../mobile && npm install && npx expo start
```

---

## Mimari

```
 Expo Go (telefon)                     FastAPI                               PostgreSQL + pgvector
 ┌──────────────────┐   JWT/HTTPS   ┌───────────────────────────┐        ┌──────────────────────────┐
 │ Giriş / Kayıt     │──────────────▶│ /api/auth  (bcrypt + JWT) │        │ users, projects          │
 │ Sohbet (RAG)      │──────────────▶│ /api/chat ─┐              │        │ documents  (standartlar) │
 │ Kaynak detayı     │               │            ▼              │        │ chunks: madde metni      │
 │ Kaydedilenler     │               │  1. Sorgu analizi (Gemini)│        │   + tsvector (EN/TR)     │
 │ Projeler / öneri  │               │  2. Hibrit arama ─────────┼──SQL──▶│   + embedding vector(768)│
 └──────────────────┘               │  3. Kaynaklı cevap (Gemini)│        │ conversations, messages  │
 Web yönetim paneli ──PDF yükle────▶│ /api/admin → ingest işçisi │        │ saved_items              │
                                     └───────────────────────────┘        └──────────────────────────┘
```

### RAG hattı — neden bu tasarım?

Havacılık/savunma standartları **hiyerarşik madde numaralarıyla** yazılır ve kullanıcıların ihtiyacı "hangi maddede, hangi sayfada?" sorusunun cevabıdır. Bu yüzden sabit uzunluklu parçalama yerine:

1. **Madde bazlı parçalama** (`backend/app/rag/parser.py`)
   - Tanınan yapılar: `4.3.2 Başlık` (MIL-STD, FAA AC, NASA), `2-3. GENERAL.` (eski FAA AC), `§ 21.17` (eCFR), `145.A.30` / `AMC1 145.A.30(e)` (EASA, SHGM), `Amaç` + `MADDE 1 –` (SHGM talimatları), `APPENDIX A` / `METHOD 501.7` / `CHAPTER 3` / `EK-1` / `BÖLÜM 2`.
   - Numara sırası tutarlılığı + yazı stili (kalın/büyük punto) ile gövde satırları başlık sanılmaz ("3 hours of exposure…").
   - Tekrarlayan üst/alt bilgiler ve içindekiler sayfaları atılır.
   - Uzun maddeler paragraf sınırından bölünür (en fazla ~420 kelime, 40 kelime örtüşme); madde atfı ve **başlık yolu** (`4 GENERAL › 4.3 Hazard analysis`) her parçada korunur.
   - Yapı bulunamazsa sayfa pencereli parçalamaya düşülür (atıf yine `s. 12` olarak kalır).
2. **Hibrit arama** (`backend/app/rag/search.py`)
   - Tam metin: `tsvector` = kod/madde no (A) + başlık yolu (A) + içerik (B, dile göre `english`/`turkish` kök bulma) + içerik (`simple`, kesin terimler için).
   - Vektör: Gemini embedding + pgvector HNSW (kosinüs).
   - **Reciprocal Rank Fusion** ile birleştirme; soruda geçen standart/madde kodu ("MIL-STD-461G", "RE102", "145.A.30"), proje alanları ve kaydedilen standartlar için ek puan.
   - Türkçe soru ↔ İngilizce standart: Gemini sorguyu bağımsız hale getirir ve İngilizce/Türkçe anahtar terimler üretir (çapraz dil tam metin araması).
3. **Kaynaklı cevap** (`backend/app/rag/answer.py`): Gemini yalnızca getirilen maddelere dayanarak, her hükmü `[n]` atfıyla yazar. Geçersiz atıflar temizlenir; uygulama atıfları **"Kaynak detayı"** paneline bağlar (madde metni, sürüm, vurgulu orijinal sayfa görüntüsü, PDF).
4. **Gemini anahtarı yoksa** sistem durmaz: yalnızca tam metin arama ve alıntı tabanlı cevap üretilir; anahtar eklenince eksik embedding'ler otomatik tamamlanır.

---

## Özellikler

- **Kayıt/giriş** (kullanıcı adı + e-posta, KVKK onayı), JWT, kullanıcı adıyla da giriş, profil düzenleme
- **Sohbet**: kaynak filtresi (FAA / SHGM / DoD / EASA…), örnek sorular, takip soruları (sohbet bağlamı), "N kaynak tarandı", atıf etiketleri
- **Kaynak detayı**: madde metni, sürüm, sayfa; **orijinal PDF sayfası madde vurgulanmış olarak**; PDF'i ilgili sayfada açma; önceki/sonraki madde
- **Kaydedilenler**: yanıtlar, standartlar/maddeler ve sohbetler
- **Proje profilleri**: proje açıklaması + çalışma alanlarına göre "bilmen gereken standartlar" ve kritik maddeler; sohbeti projeye göre önceliklendirme
- **Sohbet geçmişi**: arama, gün gruplama, yıldızlama, silme
- **Tema**: Sistem / Açık / Koyu (Figma "Theme & Overlays")
- **Web yönetim paneli**: PDF yükleme (sürükle-bırak), indeksleme ilerlemesi, yeniden indeksleme, silme, arama testi

## Hazır gelen standartlar (`backend/data/standards_catalog.json`)

| Kod | Konu | Kaynak |
|---|---|---|
| AC 20-115D | Avionik yazılım güvencesi (DO-178C kabulü) | FAA |
| AC 20-152A | Elektronik donanım güvencesi (DO-254) | FAA |
| AC 20-174 | Sivil hava aracı ve sistem geliştirme (ARP4754A) | FAA |
| AC 25.1309-1B / AC 23.1309-1E | Sistem tasarımı ve emniyet analizi | FAA |
| AC 120-92B | Emniyet Yönetim Sistemi (SMS) | FAA |
| SHT-145 | Onaylı Hava Aracı Bakım Kuruluşları Talimatı | SHGM |
| SHT-17.3 | Havacılık işletmeleri güvenlik yönetimi | SHGM |
| MIL-STD-882E | Sistem emniyeti | DoD |
| MIL-STD-461G | EMI/EMC gereksinimleri | DoD |
| MIL-HDBK-516C | Uçuşa elverişlilik sertifikasyon kriterleri | DoD |
| MIL-STD-810H *(isteğe bağlı, ~62 MB)* | Çevresel testler | DoD — `python -m app.cli seed --all` |

> **Lisans notu:** DO-178C, DO-254, ARP4754A, AS9100, ISO gibi standartlar ücretli/telif korumalıdır; projeye eklenmedi. Kurumunuzun lisanslı kopyalarını yönetim panelinden yükleyebilirsiniz.

## Komutlar

```bash
docker compose exec api python -m app.cli status            # doküman durumları
docker compose exec api python -m app.cli seed --all         # büyük standartlar dahil indir
docker compose exec api python -m app.cli reindex            # anahtar sonradan eklendiyse embedding tamamla
docker compose logs -f api                                   # API kayıtları
```

## Testler

```bash
cd backend && pip install pytest reportlab
TEST_DATABASE_URL=postgresql://postgres:postgres@localhost:5432/aerostd_test pytest -q   # 9 test: ayrıştırıcı + uçtan uca API
cd mobile && npx tsc --noEmit                                                            # tip kontrolü
```

## Klasör yapısı

```
backend/
  app/main.py            FastAPI, Swagger, yaşam döngüsü (şema, admin, işçi, otomatik indirme)
  app/schema.sql         PostgreSQL şeması (pgvector, tsvector, HNSW/GIN indeksleri)
  app/routers/           auth, documents+search, chat, projects, saved, admin
  app/rag/               parser (madde bazlı), ingest (işçi), search (hibrit/RRF), gemini, answer
  app/static/admin/      Web yönetim paneli
  data/standards_catalog.json
  tests/                 ayrıştırıcı ve uçtan uca API testleri
mobile/
  src/app/               Expo Router ekranları: (auth)/login, register · (app)/home, chat/[id], history,
                         saved, profile, library, document/[id], source/[id], projects, project/[id], project/edit
  src/components/        Tasarım sistemi (ui.tsx), ChatView, overlays (çekmece, tema, kaynak detayı)
  src/theme/             Figma "Foundations" tokenları + açık/koyu tema
  src/lib/               API istemcisi, oturum (SecureStore), tipler
```
