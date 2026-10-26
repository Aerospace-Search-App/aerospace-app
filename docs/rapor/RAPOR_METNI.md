# PDF metni — API İskeleti (Swagger) · Kağan Bayrak

> Bu dosya PDF'in **içerik kaynağıdır** (manager yazar). `rapor.html` bu metinden üretilir; metin değişirse önce burası değişir.
> `[KUTU: ...]` = vurgulu bilgi kutusu, `[KART: ...]` = rakam kartı, `[ŞEKİL: dosya]` = ekran görüntüsü, `[DİYAGRAM: ...]` = HTML/CSS ile çizilecek şema.

---

## KAPAK

**API İskeleti (Swagger)**
Aerospace Compliance Platform · Mobil Uygulama Arka Ucu

Hazırlayan: **Kağan Bayrak** — API iskeleti sorumlusu
Ders: Mobil Uygulamalar · Ekip projesi
Tarih: 27 Ekim 2026

[KART: **20** endpoint] [KART: **5** grup] [KART: **652** otomatik test] [KART: **4** ekip arkadaşı için hazır takma noktası]

Kısa özet (kapakta, 2 cümle):
Mobil uygulamamızın sunucuyla iletişim kuracağı 20 endpoint'lik API'yi kurdum ve Swagger ile belgeledim. Şu an sahte verilerle
uçtan uca çalışıyor; ekip arkadaşlarım kendi parçalarını hazır bıraktığım yerlere takarak gerçeğe çevirecek.

**İçindekiler** (kapakta veya 2. sayfa başında, sayfa numarasız sade liste)
1. Ne yaptım? · 2. Proje ve problem · 3. Kullanılan teknolojiler · 4. Sistem nasıl çalışıyor? · 5. API uç noktaları ·
6. Takma noktaları · 7. Ortak kurallar · 8. Swagger ile test · 9. Kalite ve testler · 10. Mobil ekip için bağlanma ve sonraki adımlar
Ek: Küçük sözlük

---

## 1. Ne yaptım?

Ekibimiz havacılık standartları üzerine çalışan bir mobil uygulama geliştiriyor. Mobil uygulamanın ekranları kendi
başına bilgi üretemez; verileri bir **sunucudan** ister. Sunucunun dışarıya sunduğu, hangi isteğe hangi cevabı
vereceği önceden tanımlanmış istek noktalarının tamamına **API** (Application Programming Interface) denir.

Benim görevim bu API'nin **iskeletini** kurmaktı:
- **20 endpoint** (yöntem + adres çifti) tasarladım ve çalışır hale getirdim: standartlar, arama, sohbet, raporlar, giriş.
- Her endpoint'in ne istediğini ve ne döndürdüğünü **Swagger** sayfasında otomatik belgeledim. Mobil ekip bu sayfayı
  kullanım kılavuzu olarak okuyor ve tarayıcıdan deneyebiliyor.
- Veritabanı, akıllı arama ve yapay zekâ henüz hazır olmadığı için bunların yerine **sahte (mock)** parçalar koydum.
  Böylece uygulama bugünden uçtan uca çalışıyor.
- Ekip arkadaşlarımın parçalarını takacağı yerleri **tek bir noktada** topladım ve kodda isimleriyle işaretledim.

[KUTU — Özetle] İskelet, API'nin tüm sözleşmesini (adresler, istek/cevap formatları, hata kuralları) bugünden
sabitler. Gerçek bileşenler hazır oldukça mock'ların yerini alır; mobil uygulamanın gördüğü format değişmez.

---

## 2. Proje ve problem

**Problem.** Havacılık ve savunmada bir ürün (telsiz, radar, uçuş yazılımı) teslim edilmeden önce standartlara
uyduğunu kanıtlamak zorundadır. Bu standartlar çok büyüktür (MIL-STD-810H yaklaşık 1000 sayfa), İngilizcedir ve
birbirine atıf yapar. Gözden kaçan tek bir madde test tekrarına, gecikmeye ya da sertifika reddine yol açabilir.

**Platformun iki işi:**
| Özellik | Kullanıcı ne yapar? | Sistem ne döndürür? |
|---|---|---|
| Standart asistanı | Doğal dille soru sorar: "Vibrasyon testi kaç saat sürmeli?" | Türkçe cevap + **kaynak** (standart, madde, sayfa) |
| Uyumluluk ön kontrolü | Kendi test raporunu yükler | Karar (Uyumlu / Kısmen Uyumlu / Uyumsuz / Yetersiz Bilgi), gerekçe, güven skoru |

**Projedeki standartlar**
| Kod | Konusu |
|---|---|
| MIL-STD-810H | Çevresel testler: sıcaklık, nem, titreşim, şok |
| MIL-STD-461G | Elektromanyetik uyumluluk (cihazların birbirini bozmaması) |
| DO-178C | Uçuş yazılımı sertifikasyonu |

**RAG nedir? (bir paragraf)** Cevaplar RAG (Retrieval-Augmented Generation, "bulup okuyarak cevap üretme") ile
üretilir. Sistem önce soruyla ilgili standart parçalarını **bulur**, sonra yapay zekâya "sadece bu parçalara dayanarak
cevap ver ve kaynak göster" der. Model genel bilgisinden değil, bulunan parçalardan cevap ürettiği için her cevapta
kaynak (standart, madde, sayfa) gösterilebilir.

[KUTU — Sınır] Platform bir asistandır, resmi onay mercii değildir. Kaynak gösterimi bu yüzden zorunludur.

---

## 3. Kullanılan teknolojiler

| Teknoloji | Ne işe yarıyor? |
|---|---|
| Python 3.14 | Projenin programlama dili |
| FastAPI 0.162 | API'yi yazdığımız çatı (framework). Endpoint'leri tanımlar, gelen isteği doğrular, Swagger'ı otomatik üretir |
| Pydantic 2.14 | İstek ve cevapların **şablonunu** (şema) tanımlar; hatalı veriyi servise ulaşmadan reddeder |
| Swagger / OpenAPI | API'nin otomatik, tıklanabilir kullanım kılavuzu (`/docs`). Mobil ekibin ana dokümanı |
| Uvicorn 0.54 | API'yi çalıştıran sunucu programı |
| pydantic-settings 2.16 | Ayarları (`.env`) güvenli ve tek yerden okur |
| python-multipart | PDF yüklemeyi (dosya gönderimini) mümkün kılar |
| Loguru 0.7 | Sunucu günlüğü (log): ne oldu, ne zaman oldu |
| pytest 9.1 + httpx | Otomatik testler: 652 test her değişiklikte tek komutla çalışır |
| Playwright 1.64 | Bu rapordaki Swagger ekran görüntülerini ve PDF'i otomatik üretir |

**Bu hafta bilerek olmayanlar:** Veritabanı (Doruk), vektör arama (Sudenur), Gemini yapay zekâsı. Hepsinin yerinde
şimdilik bellek-içi sahte bir parça çalışıyor.

---

## 4. Sistem nasıl çalışıyor?

### 4.1 Katmanlar
Kod dört katmana ayrıldı (Clean Architecture). Her katmanın tek bir sorumluluğu var ve bağımlılık hep **içe** doğru.

[DİYAGRAM: Dört yatay/iç içe kutu, solda katman adı, sağda klasör ve görev]
- **API** — `src/api/` — İsteği alır, şemaya göre kontrol eder, servisi çağırır, cevabı döner. İş mantığı yoktur.
- **Application** — `src/application/` — İş kuralları ("aynı standart iki kez eklenemez", "başkasının raporu görünmez") ve istek/cevap şemaları.
- **Domain** — `src/domain/` — Temel kavramlar (Standart, Rapor, Sohbet) ve **arayüzler**. Hiçbir dış kütüphaneye bağlı değildir.
- **Infrastructure** — `src/infrastructure/` — Arayüzlerin implementasyonları: bugün bellek-içi depo, mock arama, mock yapay zekâ, PDF deposu; ileride gerçekleri.
- Yan kutu: **Core** — `src/core/` — Ayarlar, tek tip hata yönetimi, bileşen seçim dosyası `deps.py`.

[KUTU — Neden katmanlı?] Her katman yalnızca bir alttakinin arayüzünü bilir. Bu sayede bir implementasyon
(ör. mock arama yerine hibrit arama) değiştiğinde iş kuralları ve API katmanı etkilenmez; her katman ayrı test edilebilir.

### 4.2 Bir sorunun yolculuğu
Mobil uygulamada "Vibrasyon testi kaç saat sürmeli?" yazıldığında:

[DİYAGRAM: numaralı yatay/dikey akış — 7 adım]
| Adım | Nerede? | Ne olur? |
|---|---|---|
| 1 | Mobil | `POST /api/v1/chat/ask` isteği gönderilir: `{"question": "Vibrasyon testi kaç saat sürmeli?"}` |
| 2 | API (router) | Şema kontrolü: soru 3–2000 karakter mi? Değilse hemen `422` döner, servise hiç gidilmez |
| 3 | Servis | Sohbet bulunur ya da yenisi açılır |
| 4 | Arama (bugün mock, yarın Sudenur) | Soruyla ilgili standart parçaları bulunur: MIL-STD-810H · Method 514.8 · Sayfa 412 |
| 5 | Yapay zekâ (bugün mock, yarın Gemini) | Parçalara dayanarak cevap yazılır. Mock cevaplar `[DEMO]` ile başlar |
| 6 | Depo (bugün bellek, yarın Doruk'un PostgreSQL'i) | Soru, cevap ve kaynaklar sohbet geçmişine kaydedilir |
| 7 | Mobil | Cevap + kaynak listesi + durum (`ANSWERED`) gelir |

Üç olası durum (hepsi `200`, mobil `status` alanına bakar):
- `ANSWERED` — cevap ve kaynaklar var.
- `NO_RESULTS` — ilgili parça bulunamadı; `answer` boş (`null`), yapay zekâ hiç çağrılmaz.
- `LLM_UNAVAILABLE` — kaynaklar bulundu ama yapay zekâ cevap üretemedi; mobil "kaynaklar bulundu, cevap üretilemedi" gösterir.

---

## 5. API uç noktaları (20)

Swagger'da 5 grup altında. Kilit simgeli uçlar giriş ister (bu hafta otomatik demo kullanıcı ile açık).

**System**
| Yöntem | Adres | Görevi |
|---|---|---|
| GET | `/` | Uygulama bilgisi (ad, sürüm, doküman adresi) |
| GET | `/health` | Sağlık kontrolü: sunucu ayakta mı, hangi arama/yapay zekâ takılı |
| GET | `/api/v1/meta/enums` | Açılır listeler için seçenekler ve sınırlar (ör. "Kısmen Uyumlu" etiketi) |

**Auth (Taha'nın modülünün şu anki şekli)**
| Yöntem | Adres | Görevi |
|---|---|---|
| POST | `/auth/register` | Kayıt ol |
| POST | `/auth/login` | Giriş yap, token al |
| POST | `/auth/refresh` | Süresi dolan token'ı yenile |
| GET | `/auth/me` | Giriş yapmış kullanıcının bilgisi |

**Standards**
| Yöntem | Adres | Görevi |
|---|---|---|
| GET | `/api/v1/standards` | Standartları listele (arama, filtre, sayfalama) |
| POST | `/api/v1/standards` | Yeni standart ekle (yönetici) |
| GET | `/api/v1/standards/{standard_id}` | Standart detayı |
| POST | `/api/v1/standards/{standard_id}/document` | Standardın PDF'ini yükle; arka planda indekslenir (yönetici) |
| GET | `/api/v1/standards/{standard_id}/index-status` | İndeksleme ne durumda? (`PENDING → PROCESSING → INDEXED`) |

**Search & Chat**
| Yöntem | Adres | Görevi |
|---|---|---|
| POST | `/api/v1/search` | Standartlarda ara (yapay zekâsız ham sonuçlar) |
| POST | `/api/v1/chat/ask` | Soru sor, kaynaklı cevap al |
| GET | `/api/v1/chat/conversations` | Sohbetlerim |
| GET | `/api/v1/chat/conversations/{conversation_id}` | Bir sohbetin tüm mesajları |

**Reports**
| Yöntem | Adres | Görevi |
|---|---|---|
| POST | `/api/v1/reports` | Rapor (PDF) yükle; arka planda işlenir |
| GET | `/api/v1/reports` | Raporlarım |
| GET | `/api/v1/reports/{report_id}` | Rapor detayı ve durumu (`UPLOADED → PROCESSING → READY`) |
| POST | `/api/v1/reports/{report_id}/analyses` | Raporu standarda göre uyumluluk analizinden geçir |

[KUTU — Auth notu] Auth uçları Taha'nın modülünün şu anki halini gösterir (`/auth/*`). Birleştirmede tek satırla
`/api/v1/auth/*` altına alınacak ve cevaba kullanıcı rolü eklenecek; mobil için kırıcı bir değişiklik değildir.

---

## 6. Takma noktaları: arkadaşlarım nereye bağlanıyor?

Her dış bileşen bir **arayüzün** (interface) arkasında. Hangi parçanın takılı olduğu tek bir dosyada seçiliyor:
`src/core/deps.py`. Kodda her kişinin yeri `TODO(İsim)` ile işaretli.

| Kişi | Görevi | İskeletteki yeri | Bugün takılı olan |
|---|---|---|---|
| Taha | Kayıt/giriş, JWT | `src/core/security.py`, `auth_service.py`, `get_current_user` | Sahte token, demo kullanıcı |
| Doruk | PostgreSQL veritabanı | Depo arayüzleri (`src/domain/interfaces.py`) | Bellek-içi depolar + örnek veri |
| Sudenur | Madde bazlı parçalama, hibrit arama | `SearchService` arayüzü | `mock_search.py` (sabit parça kataloğu) |
| Onur | Standart PDF'leri, web sohbet | `POST .../document`, `POST /chat/ask`, PDF deposu | Yerel PDF deposu |
| Şeyma, Ammar | Mobil ekranlar | Swagger + sözleşme (`docs/API_CONTRACT.md`) | Tüm ekranlar sahte veriyle çalışıyor |
| (Gemini) | Yapay zekâ cevabı ve analiz | `LLMClient` arayüzü | `mock_llm.py` (`[DEMO]` cevaplar) |

[DİYAGRAM: Ortada "Servisler" kutusu; etrafında 4 arayüz kartı: Depo · Arama · Yapay zekâ · Dosya deposu.
Her kartta "Bugün: mock ..." etiketi ve oktan sonra "Hedef: PostgreSQL (Doruk) / Hibrit arama (Sudenur) / Gemini / ..." etiketi.]

**Neden önemli?** Sudenur gerçek aramasını yazınca sadece `deps.py`'de mock yerine kendi sınıfını seçecek.
Router'lara, servislere ve mobil uygulamaya **dokunulmayacak**. Herkes birbirini beklemeden paralel çalışabiliyor.

---

## 7. Ortak kurallar

### 7.1 `/api/v1` — neden sürüm numarası?
`api` bu adreslerin veri servisi olduğunu belirtir (dokümantasyon ve diğer sayfalardan ayırır). `v1` sürümdür: telefonlardaki uygulamalar zorla güncellenemez.
Formatı değiştirmemiz gerekirse `v2` açarız; eski uygulamalar `v1` ile çalışmaya devam eder.

### 7.2 Tek tip hata formatı
Ne ters giderse gitsin cevap aynı biçimdedir:
```json
{ "error": { "code": "NOT_FOUND", "message": "Standart bulunamadı: id=7", "details": null } }
```
- `code` program içindir (mobil buna göre karar verir), `message` kullanıcı için Türkçedir.
- Sunucu hatasında (500) iç ayrıntı (stack trace) kullanıcıya **gönderilmez**, sadece günlüğe yazılır.

| Kod | HTTP | Ne zaman? |
|---|---|---|
| `VALIDATION_ERROR` | 422 | Eksik/yanlış alan (ör. soru 3 karakterden kısa) |
| `UNAUTHORIZED` / `FORBIDDEN` | 401 / 403 | Giriş yok / yetki yok |
| `NOT_FOUND` | 404 | Kayıt yok (veya başkasına ait) |
| `CONFLICT` | 409 | Aynı standart kodu zaten var; rapor analize hazır değil |
| `PAYLOAD_TOO_LARGE` / `UNSUPPORTED_FILE` | 413 / 415 | Dosya çok büyük / PDF değil |
| `LLM_UNAVAILABLE` | 503 | Yapay zekâ şu an cevap veremiyor |

### 7.3 Sayfalama
Listeler parça parça gelir: `?page=1&page_size=20` → `{items, total, page, page_size}`. En fazla 100.
Mobil cihaz tüm kayıtları tek seferde indirmez; veri kullanımı ve bekleme süresi düşük kalır.

### 7.4 Uzun işler: 202 + durum sorgulama
PDF yükleyince sunucu hemen `202 Accepted` ("aldım") der ve işi arka planda yapar. Mobil iki saniyede bir durum
adresini sorar, `INDEXED` / `READY` / `FAILED` olunca durur. Böylece büyük bir PDF işlenirken istek zaman aşımına
uğramaz ve mobil arayüz donmaz.

### 7.5 Güvenlik önlemleri
- Yüklenen dosyanın adı diske kullanılmaz; rastgele bir ad verilir (`uuid.pdf`). Böylece `../` gibi hilelerle başka klasöre yazılamaz.
- Dosyanın gerçekten PDF olduğu ilk baytlarından (`%PDF`) kontrol edilir; boyut sınırı 50 MB.
- Başkasının raporu veya sohbeti istenirse `404` döner (403 değil): "yasak" demek kaydın var olduğunu ele verirdi.
- Önce kontrol, sonra yazma: standart yoksa ya da dosya hatalıysa diske hiçbir şey yazılmaz.
- Gizli ayarlar `.env` dosyasında durur ve projeye eklenmez; örnek ayarlar `.env.example`'da.

---

## 8. Swagger ile test

Aşağıdaki ekran görüntüleri, ayrı bir test portunda çalıştırılan sunucunun Swagger sayfasından (`/docs`)
`tools/screenshots.py` ile otomatik alındı. Her biri "Try it out → Execute" ile gerçek bir istek ve gerçek cevaptır;
okunurluk için görüntülerde yalnızca istek, durum kodu ve JSON cevap bırakıldı.

[ŞEKİL: 01_swagger_genel.png] **Şekil 1 – Swagger ana sayfası.** 20 endpoint beş grup altında. Sağ üstteki
"Authorize" butonu Taha'nın token'ı için hazır; bu hafta giriş kapalı, demo kullanıcıyla çalışılıyor.

[ŞEKİL: 02_health.png] **Şekil 2 – Sağlık kontrolü.** Mobil açılışta sunucunun ayakta olduğunu buradan anlar.
`search: "mock"` ve `llm: "mock"` hangi parçaların takılı olduğunu gösterir.

[ŞEKİL: 03_standart_liste.png] **Şekil 3 – Standartları listeleme.** Cevap sayfalı gelir: `items` kayıtlar, `total`
toplam sayı. Uygulama örnek standartlarla dolu başlar.

[ŞEKİL: 04_standart_ekle_201.png] **Şekil 4 – Yeni standart ekleme (201 Created).** RTCA-DO-160G eklendi; sistem
ona bir numara (id) ve durum alanları verdi. Henüz PDF'i olmadığı için `NOT_INDEXED`.

[ŞEKİL: 05_hata_409.png] **Şekil 5 – Aynı kodla tekrar ekleme (409 Conflict).** Kod küçük harfle yazılsa da
yakalanır. Hata, tek tip formatta ve Türkçe mesajla döner.

[ŞEKİL: 06_pdf_yukle_202.png] **Şekil 6 – PDF yükleme (202 Accepted).** Sunucu dosyayı aldı ve hemen `PENDING`
döndü; indeksleme arka planda yapılıyor, telefon beklemiyor.

[ŞEKİL: 07_index_status.png] **Şekil 7 – İndeksleme durumu.** Birkaç saniye sonra durum `INDEXED`; sayfa ve parça
sayıları doldu. Mobil bu adresi `INDEXED` olana kadar yoklar.

[ŞEKİL: 08_chat_ask.png] **Şekil 8 – Kaynaklı soru-cevap.** Cevap `[DEMO]` ile başlıyor (sahte yapay zekâ) ve
MIL-STD-810H · Method 514.8 · Sayfa 412 kaynağını gösteriyor. Gerçek arama ve Gemini takılınca biçim aynı kalacak.

[ŞEKİL: 09_rapor_analiz_201.png] **Şekil 9 – Uyumluluk analizi (201 Created).** Hazır örnek rapor analiz edildi:
karar, Türkçe etiketi, güven skoru ve gerekçe döndü. Sahte modda karar bilerek "Yetersiz Bilgi".

[ŞEKİL: 10_hata_422.png] **Şekil 10 – Hatalı istek (422).** Soru 3 karakterden kısa olduğu için istek servise hiç
ulaşmadan reddedildi; `details` hangi alanın (`body.question`) neden hatalı olduğunu söylüyor. Üst mesaj
Türkçedir; alan açıklaması doğrulama kütüphanesinden İngilizce gelir (mobil kullanıcıya `message` gösterilir).

[ŞEKİL: 11_sohbet_gecmisi.png] **Şekil 11 – Sohbet geçmişi.** Şekil 8'deki soru otomatik olarak yeni bir sohbet
açtı; başlık sorunun ilk cümlesinden geliyor.

[ŞEKİL: 12_auth_login.png] **Şekil 12 – Giriş (stub).** Demo hesapla giriş yapılıp token alındı. Token şimdilik
sahte; gerçek JWT'yi Taha bağlayacak, cevabın biçimi değişmeyecek.

---

## 9. Kalite ve testler

[KART: **652** test geçti] [KART: **0** hata] [KART: **20/20** endpoint sözleşmeyle birebir]

- 652 testin yanında 3 test bilinçli olarak atlanır: üç küçük iç şemada örnek değer model düzeyinde değil alan
  düzeyinde tanımlıdır ve bu örnekler başka bir testte ayrıca doğrulanır.
- **Sözleşme önce:** Tüm formatlar önce `docs/API_CONTRACT.md` dosyasına yazıldı, kod ona göre yapıldı. Mobil ekip
  ile backend aynı belgeden çalışıyor.
- **Sözleşme kapsama testi:** Sözleşmedeki 20 endpoint'in kodda birebir var olduğunu (eksik ve fazla olmadığını)
  otomatik kontrol ediyor.
- **Her endpoint için** hem doğru kullanım hem en az bir hata durumu test edildi; tüm hataların tek tip formatta
  döndüğü ve tarihlerin UTC olduğu doğrulandı.

**Testlerin yakaladığı ve düzeltilen hatalar (dürüst not):**
| Bulunan hata | Neden önemliydi? | Durum |
|---|---|---|
| Sadece boşluktan oluşan standart kodu (`"   "`) kabul ediliyordu | Katalogda adı boş bir kayıt oluşuyordu | Düzeltildi → 422 |
| "TİTREŞİM" araması "Titreşim"i bulmuyordu | Türkçe İ/ı harfleri; mobil kullanıcı büyük harfle arayabilir | Düzeltildi |
| Sohbete var olmayan standart numarası yazılıyordu | Geçmişte tutarsız veri | Düzeltildi |
| Dosya yükleme kodu git'e eklenmiyordu (`.gitignore` kuralı) | Projeyi indiren uygulamayı çalıştıramazdı | Commit öncesi yakalandı |

**Eski projeden öğrendiklerimiz:** Önceki sürümde analiz uç noktası her zaman hata (500) dönüyordu, hata
durumları kayboluyordu, dosya adları doğrudan diske yazılıyordu. Yeni iskelette bunların her biri için bir kural
ve test var.

---

## 10. Mobil ekip için bağlanma ve sonraki adımlar

### 10.1 Bağlanma
| Nereden? | Adres |
|---|---|
| Sunucunun çalıştığı bilgisayar | `http://localhost:8000/docs` |
| Aynı Wi-Fi'daki başka bilgisayar / telefon | `http://<bilgisayarın IP'si>:8000` (ör. `192.168.1.100`; `ipconfig` ile bulunur) |
| Android emülatör (aynı bilgisayarda) | `http://10.0.2.2:8000` |

Sunucuyu başlatma: `.venv\Scripts\python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000`
(`--host 0.0.0.0` başka cihazların bağlanabilmesi için; Windows güvenlik duvarında "Özel ağ" izni verilmeli.)

### 10.2 Bilinmesi gerekenler
- Veriler bellekte tutulur: sunucu yeniden başlayınca başlangıç verisine döner (3 standart, 1 örnek rapor).
- Giriş bu hafta kapalı; herkes aynı demo kullanıcıdır. Giriş denemek için: `demo@aerospace.local` / `demo12345`.
- Açılır listelerdeki seçenekler uygulamaya gömülmemeli, `GET /api/v1/meta/enums`'tan alınmalı.
- Yükleme sonrası iki saniyede bir durum sorgulanmalı (Bölüm 7.4).
- `/openapi.json` dosyasından mobil için istemci kodu otomatik üretilebilir.

### 10.3 Sonraki adımlar
| Sıra | Kim | Ne |
|---|---|---|
| 1 | Taha | Gerçek JWT; auth uçlarını `/api/v1/auth` altına alma |
| 2 | Doruk | Bellek-içi depolar yerine PostgreSQL |
| 3 | Sudenur | Madde bazlı parçalama ve hibrit arama (`SearchService`) |
| 4 | Onur | Gerçek standart PDF'leri, web sohbet ekranının `/chat/ask`'e bağlanması |
| 5 | Şeyma, Ammar | Giriş/kayıt ve sohbet ekranlarının Swagger'daki formatla bağlanması |
| 6 | Kağan | Kalan 12 endpoint (güncelleme, silme, PDF görüntüleme, analiz geçmişi) |

---

## Ek: Küçük sözlük
| Terim | Bir cümlede |
|---|---|
| API | Bir programın diğer programlara sunduğu tanımlı istek noktalarının tamamı |
| Endpoint | Tek bir istek noktası: yöntem + adres (ör. `GET /health`) |
| Swagger / OpenAPI | API'nin otomatik, tıklanabilir kullanım kılavuzu |
| Şema | Gelen/giden verinin şablonu (hangi alan, hangi tip, hangi sınır) |
| Mock | Gerçeğinin yerine geçici takılan sahte parça |
| Arayüz (interface) | Bir bileşenin sağlaması gereken metotların tanımı; implementasyonu değiştirilebilir |
| RAG | Önce ilgili belge parçalarını bulup sonra onlara dayanarak cevap üretme |
| Token / JWT | Girişten sonra sunucunun verdiği ve her istekte gönderilen imzalı kimlik bilgisi |
| HTTP durum kodu | Cevabın sonucu: 200 tamam, 201 oluşturuldu, 202 alındı, 404 yok, 422 hatalı istek |
