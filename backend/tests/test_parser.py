from pathlib import Path

import pytest

from app.rag.parser import MAX_WORDS, parse_pdf

from .samples import make_easa, make_milstd, make_shgm, make_unstructured


@pytest.fixture(scope="module")
def tmp(tmp_path_factory) -> Path:
    return tmp_path_factory.mktemp("pdfs")


def refs(parsed):
    return [c.clause_ref for c in parsed.chunks]


def test_milstd_clauses(tmp):
    p = parse_pdf(make_milstd(tmp / "mil.pdf"))
    r = refs(p)
    assert p.structured
    for ref in ["1.1", "1.2", "2.", "4.1", "4.1.1", "4.2", "A.1"]:
        assert any(x.rstrip(".") == ref.rstrip(".") for x in r), (ref, r)
    # içindekiler ve üst bilgi satırları içerikte olmamalı
    joined = " ".join(c.content for c in p.chunks)
    assert "....." not in joined
    assert "MIL-STD-999X MIL-STD-999X" not in joined
    # "3 hours of exposure" gövde satırı başlık sanılmamalı
    assert "3" not in r
    # Uzun madde bölünmeli, atıf korunmalı
    tracking = [c for c in p.chunks if c.clause_ref == "4.1.1"]
    assert len(tracking) >= 2 and all(c.word_count <= MAX_WORDS + 5 for c in tracking)
    assert tracking[0].heading.startswith("Hazard tracking")
    # Başlık yolu üst maddeleri içermeli
    assert "4 GENERAL REQUIREMENTS" in tracking[0].heading_path
    appendix = [c for c in p.chunks if c.clause_ref == "A.1"][0]
    assert appendix.heading_path.startswith("Appendix A")


def test_shgm_madde(tmp):
    p = parse_pdf(make_shgm(tmp / "sht.pdf"))
    by_ref = {c.clause_ref: c for c in p.chunks}
    assert {"Madde 1", "Madde 2", "Madde 3"} <= set(by_ref)
    assert by_ref["Madde 1"].heading == "Amaç"
    assert by_ref["Madde 3"].heading == "Personel gereklilikleri"
    assert "Kapsam" not in by_ref["Madde 1"].content.split("\n")[-1]


def test_easa(tmp):
    p = parse_pdf(make_easa(tmp / "easa.pdf"))
    r = refs(p)
    assert "145.A.25" in r and "145.A.30" in r and "AMC1 145.A.30(e)" in r


def test_unstructured_fallback(tmp):
    p = parse_pdf(make_unstructured(tmp / "u.pdf"))
    assert not p.structured
    assert p.chunks and p.chunks[0].clause_ref.startswith("s. ")


def test_faa_ac_styles(tmp):
    from .samples import make_faa_ac

    p = parse_pdf(make_faa_ac(tmp / "ac.pdf"))
    by_ref = {c.clause_ref: c for c in p.chunks}
    assert "1" in by_ref and by_ref["1"].heading.startswith("Purpose of this Advisory Circular")
    assert "a. Applicability" in by_ref["1"].content  # alt paragraf aynı maddede kalır
    assert "2" in by_ref
    assert by_ref["3-1"].heading == "GENERAL" and "Tool qualification is required" in by_ref["3-1"].content
    assert by_ref["3-2"].heading == "CRITERIA"
    assert by_ref["3-2"].heading_path.startswith("Chapter 3 TOOL QUALIFICATION")
