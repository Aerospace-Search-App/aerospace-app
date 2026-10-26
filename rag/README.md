# PDF parçalama

Standart PDF'lerini asistanın arayabileceği madde bazlı metin parçalarına böler.

1. **Metni çıkarır** (`pdfplumber`). Sayfa başına neredeyse hiç metin çıkmıyorsa PDF taranmış kabul edilir ve program 2 koduyla çıkar. Bu durumda o PDF için OCR gerekir.
2. **Madde madde böler.** `4.3.2 Pressure Vessels` gibi numaralı başlıklar ve `Annex A`, `A.1` gibi ek maddeleri parça sınırıdır. Numarası sıraya uymayan satırlar başlık sayılmaz. Örneğin bir tablo satırı ya da satır başındaki bir atıf yeni parça başlatmaz. İçindekiler sayfaları ile her sayfada tekrar eden üst/alt bilgiler atılır. 2000 karakterden uzun maddeler aynı madde numarasıyla birden çok parçaya bölünür.
3. **Her parçaya kaynak bilgisi ekler:** standart kodu, revizyon, madde numarası, madde başlığı, başlık yolu ve sayfa numarası.
4. **JSON (isteğe bağlı CSV) yazar.** Alan adları `veritabani/init/01_schema.sql` dosyasındaki `document_chunks` tablosuyla aynıdır.

## Kurulum

```bash
cd rag
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## Kullanım

```bash
python parcalama.py STANDART.pdf --kod ECSS-E-ST-32C --surum C
python parcalama.py STANDART.pdf --kod NASA-STD-5001 --surum B --cikti parcalar.json --csv
```

Örnek çıktı (bir parça):

```json
{
  "standard_code": "ORNEK-STD-001",
  "version": "A",
  "chunk_index": 6,
  "section_number": "4",
  "clause_number": "4.2.1",
  "title": "Leak Testing",
  "heading_path": "4 Requirements > 4.2 Pressure Vessels > 4.2.1 Leak Testing",
  "page_number": 4,
  "page_end": 4,
  "content": "4.2.1 Leak Testing\nEach vessel shall be leak tested after proof testing."
}
```

Hiçbir maddeye bağlanamayan metin (kapak, ön söz) `clause_number: null` ile ilk parçada yer alır.

## Test

```bash
python -m pytest
```

Testler `tests/ornek/ornek_standart.pdf` üzerinde çalışır. Bu dosya aynı klasördeki HTML'den üretildi. İçinde içindekiler sayfası, üst/alt bilgi, tablo satırı, heceyle bölünmüş kelime ve ek maddesi var.

## Bilinen sınırlar

- Tablolar düz metin olarak parçanın içine girer, satır/sütun yapısı korunmaz.
- Çok sütunlu sayfalarda satır sırası karışabilir.
- Embedding ve arama bu adımın kapsamında değil.
