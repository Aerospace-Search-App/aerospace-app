"""Standart PDF'lerini madde bazlı metin parçalarına (chunk) böler.

Kullanım:
    python parcalama.py STANDART.pdf --kod ECSS-E-ST-32C --surum C
    python parcalama.py STANDART.pdf --kod NASA-STD-5001 --surum B --cikti parcalar.json --csv

Her parça; standart kodu, revizyon, madde numarası, madde başlığı, başlık yolu
ve sayfa numarasını taşır. Çıktı alanları veritabanındaki document_chunks
tablosuyla aynı adları kullanır.

Çıkış kodları: 0 başarılı, 1 hata, 2 PDF taranmış görünüyor (OCR gerekli).
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import Counter
from dataclasses import asdict, dataclass, field
from pathlib import Path

import pdfplumber

# Sayfa başına ortalama bu kadar karakterden az metin çıkıyorsa PDF taranmış kabul edilir.
TARANMIS_ESIK = 100
# Bundan uzun maddeler satır sınırından bölünür.
MAKS_KARAKTER = 2000
# Sayfaların bu oranında tekrar eden satırlar üst/alt bilgi sayılıp atılır.
TEKRAR_ORANI = 0.6
# Ek (Annex) numaraları sayısal maddelerden sonra sıralansın diye harflere eklenen taban.
EK_TABANI = 1000

BUYUK_HARF = "A-ZÇĞİÖŞÜ"
NUMARALI_BASLIK = re.compile(rf"^(\d{{1,2}}(?:\.\d{{1,3}}){{0,5}})\.?\s+([{BUYUK_HARF}].*)$")
EK_BASLIGI = re.compile(rf"^(?:Annex|ANNEX|Appendix|APPENDIX|Ek|EK)\s+([A-Z])\b[\s.:\-–]*(.*)$")
EK_MADDESI = re.compile(rf"^([A-Z](?:\.\d{{1,3}}){{1,5}})\.?\s+([{BUYUK_HARF}].*)$")
ICINDEKILER_SATIRI = re.compile(r"(?:\.\s*){4,}\s*\d+\s*$")
SATIR_SONU_SAYFA_NO = re.compile(r"\s\d{1,4}\s*$")


@dataclass
class Parca:
    standard_code: str
    version: str | None
    chunk_index: int
    section_number: str | None
    clause_number: str | None
    title: str | None
    heading_path: str | None
    page_number: int
    page_end: int
    content: str


@dataclass
class _Madde:
    numara: str | None
    baslik: str | None
    sayfa: int
    satirlar: list[tuple[int, str]] = field(default_factory=list)


class TaranmisPdfHatasi(Exception):
    """PDF'ten neredeyse hiç metin çıkmadı; OCR gerekiyor."""


def sayfalari_oku(pdf_yolu: Path) -> list[list[str]]:
    """Her sayfanın satırlarını döndürür (sayfa sırası korunur)."""
    with pdfplumber.open(pdf_yolu) as pdf:
        return [(sayfa.extract_text() or "").splitlines() for sayfa in pdf.pages]


def taranmis_mi(sayfalar: list[list[str]]) -> bool:
    if not sayfalar:
        return True
    toplam = sum(len("".join(satirlar).strip()) for satirlar in sayfalar)
    return toplam / len(sayfalar) < TARANMIS_ESIK


def _kalip(satir: str) -> str:
    """Üst/alt bilgi karşılaştırması için rakamları sabitler ("Sayfa 3" ~ "Sayfa 4")."""
    return re.sub(r"\d+", "#", satir.strip())


def ust_alt_bilgileri_bul(sayfalar: list[list[str]]) -> set[str]:
    if len(sayfalar) < 3:
        return set()
    sayac = Counter()
    for satirlar in sayfalar:
        sayac.update({_kalip(s) for s in satirlar if s.strip()})
    esik = TEKRAR_ORANI * len(sayfalar)
    return {kalip for kalip, adet in sayac.items() if adet >= esik}


def icindekiler_sayfasi_mi(satirlar: list[str]) -> bool:
    """Satırların çoğu "başlık ...... 12" biçimindeyse sayfa içindekiler tablosudur."""
    dolu = [s for s in satirlar if s.strip()]
    if len(dolu) < 5:
        return False
    noktali = sum(1 for s in dolu if ICINDEKILER_SATIRI.search(s))
    numarali_sayfa_sonlu = sum(
        1 for s in dolu if NUMARALI_BASLIK.match(s.strip()) and SATIR_SONU_SAYFA_NO.search(s)
    )
    return noktali >= 3 or numarali_sayfa_sonlu / len(dolu) >= 0.5


def _bilesenler(numara: str) -> tuple[int, ...]:
    """"4.3.2" -> (4, 3, 2); "B.2" -> (1001, 2)."""
    parcalar = numara.split(".")
    if parcalar[0].isalpha():
        ilk = EK_TABANI + ord(parcalar[0]) - ord("A")
    else:
        ilk = int(parcalar[0])
    return (ilk, *map(int, parcalar[1:]))


def siradaki_madde_mi(aday: tuple[int, ...], simdiki: tuple[int, ...]) -> bool:
    """Aday numara, şimdiki maddeden sonra makul biçimde gelebilir mi?

    Satır başındaki "7.2 numaralı maddeye bakınız" gibi atıfları ya da tablo
    satırlarını başlık sanmamak için kullanılır. Kaçırılmış bir başlığı tolere
    etmek için bir numara atlamaya izin verilir (4.2 -> 4.4).
    """
    if aday[0] >= EK_TABANI > (simdiki[0] if simdiki else 0):
        return True  # gövdeden eklere geçiş
    i = 0
    while i < len(aday) and i < len(simdiki) and aday[i] == simdiki[i]:
        i += 1
    if i == len(aday):
        return False  # aynı madde ya da üst maddesi tekrar geçiyor
    if i == len(simdiki):
        ilk_beklenen = aday[i] in (0, 1) if i == 0 else aday[i] == 1
        return ilk_beklenen and all(b == 1 for b in aday[i + 1:])
    return simdiki[i] < aday[i] <= simdiki[i] + 2 and all(b == 1 for b in aday[i + 1:])


def _baslik_mi(baslik: str) -> bool:
    harf = sum(c.isalpha() for c in baslik)
    return harf >= 2 and not ICINDEKILER_SATIRI.search(baslik)


def maddelere_ayir(sayfalar: list[list[str]]) -> list[_Madde]:
    tekrar_edenler = ust_alt_bilgileri_bul(sayfalar)
    maddeler = [_Madde(numara=None, baslik=None, sayfa=1)]
    simdiki: tuple[int, ...] = ()

    for sayfa_no, satirlar in enumerate(sayfalar, start=1):
        if icindekiler_sayfasi_mi(satirlar):
            continue
        for ham in satirlar:
            satir = ham.strip()
            if not satir or _kalip(satir) in tekrar_edenler:
                continue

            numara = baslik = None
            if eslesme := EK_BASLIGI.match(satir):
                numara, baslik = eslesme.group(1), eslesme.group(2).strip() or None
            elif eslesme := (NUMARALI_BASLIK.match(satir) or EK_MADDESI.match(satir)):
                numara, baslik = eslesme.group(1), eslesme.group(2).strip()
                if not _baslik_mi(baslik):
                    numara = None

            if numara:
                aday = _bilesenler(numara)
                if siradaki_madde_mi(aday, simdiki):
                    simdiki = aday
                    maddeler.append(_Madde(numara=numara, baslik=baslik, sayfa=sayfa_no))
                    maddeler[-1].satirlar.append((sayfa_no, satir))
                    continue

            maddeler[-1].satirlar.append((sayfa_no, satir))

    return [m for m in maddeler if m.satirlar]


def _birlestir(satirlar: list[str]) -> str:
    """Satır sonunda heceyle bölünmüş kelimeleri ("safe-\\nty") birleştirir."""
    metin = "\n".join(satirlar)
    return re.sub(r"(\w)-\n([a-zçğıöşü])", r"\1\2", metin)


def _bol(satirlar: list[tuple[int, str]]) -> list[list[tuple[int, str]]]:
    """Uzun maddeleri, satır sınırlarından MAKS_KARAKTER'i geçmeyecek şekilde böler."""
    gruplar, grup, uzunluk = [], [], 0
    for sayfa, satir in satirlar:
        if grup and uzunluk + len(satir) > MAKS_KARAKTER:
            gruplar.append(grup)
            grup, uzunluk = [], 0
        grup.append((sayfa, satir))
        uzunluk += len(satir) + 1
    if grup:
        gruplar.append(grup)
    return gruplar


def parcala(sayfalar: list[list[str]], kod: str, surum: str | None = None) -> list[Parca]:
    if taranmis_mi(sayfalar):
        raise TaranmisPdfHatasi(
            "PDF'ten neredeyse hiç metin çıkmadı. Taranmış (resim) bir PDF olabilir, OCR gerekiyor."
        )

    basliklar: dict[str, str] = {}
    parcalar: list[Parca] = []
    for madde in maddelere_ayir(sayfalar):
        if madde.numara and madde.baslik:
            basliklar[madde.numara] = madde.baslik
        # "4 Gereksinimler" hemen ardından "4.1" geliyorsa başlık tek başına parça olmaz;
        # alt maddelerin heading_path alanında zaten yer alır.
        if madde.numara and len(madde.satirlar) == 1:
            continue
        yol = _baslik_yolu(madde.numara, basliklar)
        bolum = madde.numara.split(".")[0] if madde.numara else None

        for grup in _bol(madde.satirlar):
            icerik = _birlestir([s for _, s in grup]).strip()
            if not icerik:
                continue
            parcalar.append(
                Parca(
                    standard_code=kod,
                    version=surum,
                    chunk_index=len(parcalar),
                    section_number=bolum,
                    clause_number=madde.numara,
                    title=madde.baslik,
                    heading_path=yol,
                    page_number=grup[0][0],
                    page_end=grup[-1][0],
                    content=icerik,
                )
            )
    return parcalar


def _baslik_yolu(numara: str | None, basliklar: dict[str, str]) -> str | None:
    if not numara:
        return None
    parcalar = numara.split(".")
    yol = []
    for i in range(1, len(parcalar) + 1):
        onek = ".".join(parcalar[:i])
        if onek in basliklar:
            yol.append(f"{onek} {basliklar[onek]}")
    return " > ".join(yol) or numara


def json_yaz(parcalar: list[Parca], yol: Path) -> None:
    yol.write_text(
        json.dumps([asdict(p) for p in parcalar], ensure_ascii=False, indent=2), encoding="utf-8"
    )


def csv_yaz(parcalar: list[Parca], yol: Path) -> None:
    with yol.open("w", newline="", encoding="utf-8-sig") as f:
        yazici = csv.DictWriter(f, fieldnames=list(Parca.__dataclass_fields__))
        yazici.writeheader()
        yazici.writerows(asdict(p) for p in parcalar)


def main(argv: list[str] | None = None) -> int:
    ayrac = argparse.ArgumentParser(description="Standart PDF'ini madde bazlı parçalara böler.")
    ayrac.add_argument("pdf", type=Path, help="Standart PDF dosyası")
    ayrac.add_argument("--kod", required=True, help="Standart kodu, ör. ECSS-E-ST-32C")
    ayrac.add_argument("--surum", help="Revizyon, ör. C veya Rev.1")
    ayrac.add_argument("--cikti", type=Path, help="JSON çıktı yolu (varsayılan: PDF adı + .json)")
    ayrac.add_argument("--csv", action="store_true", help="JSON'un yanına CSV de yaz")
    arg = ayrac.parse_args(argv)

    if not arg.pdf.is_file():
        print(f"Hata: dosya bulunamadı: {arg.pdf}", file=sys.stderr)
        return 1

    try:
        parcalar = parcala(sayfalari_oku(arg.pdf), arg.kod, arg.surum)
    except TaranmisPdfHatasi as hata:
        print(f"Uyarı: {arg.pdf.name}: {hata}", file=sys.stderr)
        return 2

    cikti = arg.cikti or arg.pdf.with_suffix(".json")
    json_yaz(parcalar, cikti)
    print(f"{len(parcalar)} parça yazıldı: {cikti}")
    if arg.csv:
        csv_yolu = cikti.with_suffix(".csv")
        csv_yaz(parcalar, csv_yolu)
        print(f"CSV yazıldı: {csv_yolu}")

    numarasiz = sum(1 for p in parcalar if p.clause_number is None)
    if numarasiz:
        print(f"Not: {numarasiz} parça bir maddeye bağlanamadı (ön söz, kapak vb.).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
