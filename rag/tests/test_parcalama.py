import json
from pathlib import Path

import pytest

import parcalama
from parcalama import TaranmisPdfHatasi, parcala, siradaki_madde_mi

ORNEK_PDF = Path(__file__).parent / "ornek" / "ornek_standart.pdf"


@pytest.fixture(scope="module")
def ornek_parcalar():
    return parcala(parcalama.sayfalari_oku(ORNEK_PDF), "ORNEK-STD-001", "A")


def _madde(parcalar, numara):
    return [p for p in parcalar if p.clause_number == numara]


def test_maddeler_sirayla_bulunur(ornek_parcalar):
    numaralar = [p.clause_number for p in ornek_parcalar]
    assert numaralar == [None, "1", "2", "3", "4.1", "4.2", "4.2.1", "A.1"]


def test_icindekiler_ve_ust_alt_bilgi_atilir(ornek_parcalar):
    hepsi = "\n".join(p.content for p in ornek_parcalar)
    assert "Table of Contents" not in hepsi
    assert "......" not in hepsi
    assert "Page 3 of 4" not in hepsi
    assert "Structural Design Requirements" not in hepsi.replace(
        "Structural Design and Test Requirements", ""
    )


def test_sayfa_ve_kaynak_bilgisi(ornek_parcalar):
    (parca,) = _madde(ornek_parcalar, "4.2.1")
    assert parca.standard_code == "ORNEK-STD-001"
    assert parca.version == "A"
    assert parca.section_number == "4"
    assert parca.title == "Leak Testing"
    assert parca.heading_path == "4 Requirements > 4.2 Pressure Vessels > 4.2.1 Leak Testing"
    assert parca.page_number == 4


def test_tablo_satiri_madde_sanilmaz(ornek_parcalar):
    (parca,) = _madde(ornek_parcalar, "4.1")
    assert "3 Bolts M6 torque 12 Nm" in parca.content
    assert "Composite structures" in parca.content


def test_heceleme_birlestirilir(ornek_parcalar):
    (parca,) = _madde(ornek_parcalar, "4.2")
    assert "operating pressure before flight" in parca.content.replace("\n", " ")


def test_ek_maddesi(ornek_parcalar):
    (parca,) = _madde(ornek_parcalar, "A.1")
    assert parca.heading_path == "A Test Levels > A.1 Random Vibration"
    assert parca.section_number == "A"


def test_chunk_index_sirali(ornek_parcalar):
    assert [p.chunk_index for p in ornek_parcalar] == list(range(len(ornek_parcalar)))


@pytest.mark.parametrize(
    "aday, simdiki, beklenen",
    [
        ((1,), (), True),
        ((4, 3), (4, 2, 1), True),
        ((4, 4), (4, 2), True),  # bir başlık kaçırılmış olabilir
        ((4, 9), (4, 2), False),
        ((5, 1), (4, 4), True),
        ((3,), (4, 1), False),  # geriye gidiş: tablo satırı ya da atıf
        ((4, 2), (4, 2), False),
        ((4, 2, 1), (4, 2), True),
        ((4, 2, 3), (4, 2), False),
        ((1000, 1), (6, 2), True),  # gövdeden Ek A'ya
    ],
)
def test_siradaki_madde_mi(aday, simdiki, beklenen):
    assert siradaki_madde_mi(aday, simdiki) is beklenen


def test_uzun_madde_bolunur():
    satirlar = ["1 Scope"] + [f"Line {i} " + "x" * 90 for i in range(60)]
    parcalar = parcala([satirlar], "T")
    assert len(parcalar) > 1
    assert all(p.clause_number == "1" for p in parcalar)
    assert all(len(p.content) <= parcalama.MAKS_KARAKTER for p in parcalar)


def test_taranmis_pdf_reddedilir():
    with pytest.raises(TaranmisPdfHatasi):
        parcala([[], [""], []], "T")


def test_komut_satiri_json_ve_csv(tmp_path):
    cikti = tmp_path / "parcalar.json"
    kod = parcalama.main([str(ORNEK_PDF), "--kod", "ORNEK-STD-001", "--cikti", str(cikti), "--csv"])
    assert kod == 0
    veri = json.loads(cikti.read_text(encoding="utf-8"))
    assert veri[1]["clause_number"] == "1"
    assert cikti.with_suffix(".csv").read_text(encoding="utf-8-sig").startswith("standard_code,")
