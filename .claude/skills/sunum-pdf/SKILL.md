---
name: sunum-pdf
description: Swagger ekran görüntülerini alıp Kağan'ın 10–12 sayfalık Türkçe sunum PDF'ini üretme reçetesi. Faz 5'te, "PDF'i hazırla / ekran görüntülerini al / PDF'i güncelle" isteklerinde kullan.
---

# Sunum PDF'i reçetesi

Çıktı: `docs/rapor/Kagan_Bayrak_API_Iskeleti.pdf` + kopyası kullanıcının masaüstüne (`~/Desktop`; klasör yoksa kopya atlanır).
İçerik planı ve metin: `docs/rapor/RAPOR_METNI.md` (arka plan: `docs/TASK_API_SKELETON.md` → Faz 5). Metin `docs/rapor/RAPOR_METNI.md`'de; sen HTML'e döker, görselleri ve PDF'i üretirsin.

## 1. Kurulum (bir kez)
Playwright tarayıcı indirmeden sistemdeki Edge/Chrome'u kullanır:
```bash
.venv/Scripts/python -m pip install playwright
```
Script'lerde: `p.chromium.launch(channel="msedge")` (olmazsa `channel="chrome"`). `playwright install` gerekmez.

## 2. Ekran görüntüleri — `tools/screenshots.py`
- Sunucuyu arka planda başlat (Bash aracında `run_in_background`):
  `.venv/Scripts/python -m uvicorn main:app --port 8000`, `/health` cevap verene kadar bekle.
- Viewport 1400 genişlik, `device_scale_factor=2` (PDF'te net görünsün).
- Swagger'da her görüntü için: ilgili operasyonu aç → "Try it out" → örnek gövdeyi gir → "Execute" →
  cevap bölümü göründükten sonra **sadece o operasyon bloğunun** ekran görüntüsünü al (`locator.screenshot`).
  Operasyon id'leri `#operations-<Tag>-<operationId>` biçimindedir; `app.openapi()`'den operationId'leri oku.
- Akış sırası önemli (bellek-içi veri): önce standart ekle, sonra aynı kodla 409 al, sonra PDF yükle, sonra index-status.
- Dosyalar: `docs/rapor/img/01_swagger_genel.png`, `02_health.png`, `03_standart_liste.png`, `04_standart_ekle_201.png`,
  `05_hata_409.png`, `06_pdf_yukle_202.png`, `07_index_status.png`, `08_chat_ask.png`, `09_rapor_analiz_201.png`.
- Bitince sunucuyu durdur.

## 3. HTML — `docs/rapor/rapor.html`
Taha'nın PDF görünümü (Word benzeri):
- A4, kenar 2 cm, gövde yazısı 11pt sans-serif (Calibri / "Segoe UI" / Arial), satır aralığı 1.4.
- Bölüm başlıkları numaralı ("2. Kullanılan Teknolojiler"), lacivert-mavi renk (#1F3864 / #2E74B5), alt başlıklar açık mavi.
- Tablolar: başlık satırı lacivert zemin (#1F3864) + beyaz kalın yazı, ince gri kenarlıklar, hücre iç boşluğu.
- Görseller ortalı, genişlik ≤ %100, altında italik "Şekil N – açıklama" ve 1–2 cümle yorum.
- Kod/endpoint yolları monospace. Görseller göreli yol (`img/...`).
- `page-break-inside: avoid` tablolar ve şekiller için; büyük bölümlerden önce gerekirse `page-break-before`.
- Altbilgide sayfa numarası (Playwright `footer_template`).

## 4. PDF — `tools/build_pdf.py`
```python
page.goto(Path("docs/rapor/rapor.html").resolve().as_uri())
page.pdf(path="docs/rapor/Kagan_Bayrak_API_Iskeleti.pdf", format="A4", print_background=True,
         display_header_footer=True, header_template="<span></span>",
         footer_template='<div style="font-size:9px;width:100%;text-align:center"><span class="pageNumber"></span></div>',
         margin={"top": "20mm", "bottom": "20mm", "left": "20mm", "right": "20mm"})
```
Sonra masaüstüne kopyala.

## 5. Kendi kontrolün
- Sayfa sayısı 10–12 (fazlaysa görselleri küçült/birleştir; azsa açıklamaları genişletme — gereksiz dolgu yok).
- PDF'i Read aracıyla açıp her sayfaya bak: kesilen tablo, taşan görsel, bozuk Türkçe karakter var mı?
- Endpoint tablosu koddaki 20 endpoint'le birebir mi?
