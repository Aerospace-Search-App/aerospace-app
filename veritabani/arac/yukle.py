"""Sudenur'un parçalama çıktısını (JSON) veri tabanına yükler.

Kullanım:
    python yukle.py parcalar.json --baslik "Pressure Vessels" --kurum ECSS --yil 2020

Standart kodu ve revizyon JSON'un içindeki standard_code ve version alanlarından okunur.
Aynı (kod, revizyon) tekrar yüklenirse eski parçaları silinip yenileri yazılır, yani
betik güvenle tekrar çalıştırılabilir.

Bağlantı adresi DATABASE_URL ortam değişkeninden okunur:
    postgresql+psycopg2://app:ŞİFRE@localhost:5433/standartlar
"""
import argparse
import json
import os
import sys

from sqlalchemy import create_engine, text

# JSON'daki alanlardan veri tabanına giren sütunlar.
# title, heading_path ve page_end şemada yok; content zaten başlık satırıyla başlıyor.
PARCA_ALANLARI = ("chunk_index", "section_number", "clause_number", "page_number", "content")


def parcalari_oku(yol):
    with open(yol, encoding="utf-8") as f:
        veri = json.load(f)
    if not isinstance(veri, list) or not veri:
        raise ValueError("JSON dosyası boş ya da liste değil.")
    kodlar = {(p["standard_code"], p["version"]) for p in veri}
    if len(kodlar) != 1:
        raise ValueError(f"Dosyada birden fazla standart var: {sorted(kodlar)}")
    return kodlar.pop(), veri


def standart_ekle(baglanti, kod, surum, baslik, kurum, yil, dil, pdf_yolu):
    """Standardı ekler, varsa günceller. standard_id döner."""
    satir = baglanti.execute(
        text(
            """
            INSERT INTO standards (code, title, version, issuing_body, publication_year, language, pdf_path)
            VALUES (:kod, COALESCE(:baslik, :kod), :surum, :kurum, :yil, :dil, :pdf)
            ON CONFLICT (code, version) DO UPDATE SET
                title = COALESCE(:baslik, standards.title),
                issuing_body = COALESCE(EXCLUDED.issuing_body, standards.issuing_body),
                publication_year = COALESCE(EXCLUDED.publication_year, standards.publication_year),
                language = EXCLUDED.language,
                pdf_path = COALESCE(EXCLUDED.pdf_path, standards.pdf_path)
            RETURNING standard_id
            """
        ),
        {"kod": kod, "baslik": baslik, "surum": surum, "kurum": kurum,
         "yil": yil, "dil": dil, "pdf": pdf_yolu},
    ).one()
    return satir.standard_id


def parcalari_yukle(baglanti, standard_id, parcalar):
    # Tekrar yüklemede eski parçalar gitsin ki çift kayıt olmasın.
    baglanti.execute(text("DELETE FROM document_chunks WHERE standard_id = :s"), {"s": standard_id})
    satirlar = [
        {"s": standard_id, **{alan: p.get(alan) for alan in PARCA_ALANLARI}}
        for p in parcalar
    ]
    baglanti.execute(
        text(
            """
            INSERT INTO document_chunks
                (standard_id, chunk_index, section_number, clause_number, page_number, content)
            VALUES
                (:s, :chunk_index, :section_number, :clause_number, :page_number, :content)
            """
        ),
        satirlar,
    )
    return len(satirlar)


def main():
    ap = argparse.ArgumentParser(description="Parçalama çıktısını veri tabanına yükler.")
    ap.add_argument("json_dosyasi")
    ap.add_argument("--baslik", help="Standardın adı (verilmezse kod kullanılır)")
    ap.add_argument("--kurum", help="Yayınlayan kurum, ör. ECSS")
    ap.add_argument("--yil", type=int, help="Yayın yılı")
    ap.add_argument("--dil", default="en")
    ap.add_argument("--pdf", help="PDF dosyasının yolu")
    args = ap.parse_args()

    url = os.environ.get("DATABASE_URL")
    if not url:
        print("DATABASE_URL tanımlı değil.", file=sys.stderr)
        return 1
    try:
        (kod, surum), parcalar = parcalari_oku(args.json_dosyasi)
    except (OSError, ValueError, KeyError) as e:
        print(f"Dosya okunamadı: {e}", file=sys.stderr)
        return 1

    motor = create_engine(url)
    with motor.begin() as baglanti:  # hata olursa hepsi geri alınır
        sid = standart_ekle(baglanti, kod, surum, args.baslik, args.kurum, args.yil, args.dil, args.pdf)
        adet = parcalari_yukle(baglanti, sid, parcalar)
    print(f"{kod} ({surum}): {adet} parça yüklendi. standard_id={sid}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
