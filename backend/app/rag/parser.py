"""Standart PDF'lerini madde (clause) bazında parçalayan ayrıştırıcı.

Havacılık ve savunma standartları hiyerarşik madde numaralarıyla yazılır:
  * FAA AC / MIL-STD / NASA:  "4.", "4.3", "4.3.2.1 Başlık"
  * eCFR:                       "§ 21.17 Designation of applicable regulations."
  * EASA / SHGM (Part-145):     "145.A.30 Personnel requirements", "AMC1 145.A.30(e)"
  * SHGM talimat / yönetmelik:  "Amaç" + "MADDE 1 – (1) Bu talimatın amacı..."
  * Bölüm işaretleri:           "APPENDIX A", "METHOD 501.7", "CHAPTER 3", "EK-1", "BÖLÜM 2"

Yaklaşım:
 1. PyMuPDF ile satırlar + yazı boyutu/kalınlık bilgisi okunur.
 2. Her sayfada tekrar eden üst/alt bilgi satırları ve içindekiler sayfaları atılır.
 3. Satırlar madde başlığı mı diye regex + numara sırası tutarlılığı + yazı stili ile sınanır.
 4. Her başlık yeni bir madde başlatır; madde gövdesi bir sonraki başlığa kadar sürer.
 5. Uzun maddeler paragraf sınırlarından bölünür (part=1..n), madde atfı korunur.
 6. Hiç yapı bulunamazsa sayfa pencereli parçalamaya düşülür (yine sayfa atıflı).
"""
from __future__ import annotations

import re
import statistics
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

import pymupdf

MAX_WORDS = 420      # bir parçadaki en fazla kelime
OVERLAP_WORDS = 40   # bölünen maddelerde parçalar arası örtüşme
MIN_BODY_WORDS = 6   # bundan kısa gövdeli maddeler (salt başlık) ayrı parça olmaz

UPPER = "A-ZÇĞİÖŞÜ"
DEC_RE = re.compile(
    rf"^(?P<ref>(?:[A-Z]\.)?\d{{1,3}}(?:\.\d{{1,3}}){{0,6}})(?P<dot>\.?)\s+(?P<title>[{UPPER}\"“(][^\n]{{0,170}})$"
)
DASH_RE = re.compile(rf"^(?P<ref>\d{{1,2}}-\d{{1,3}})\.?\s+(?P<title>[{UPPER}][^\n]{{1,170}})$")  # eski FAA AC: "2-3. GENERAL."
CFR_RE = re.compile(r"^§\s*(?P<ref>\d+\.\d+[a-z]?)\s+(?P<title>.{2,170})$")
EASA_RE = re.compile(
    rf"^(?P<ref>(?:(?:AMC|GM)\d*\s+)?\d{{2,3}}\.[A-Z]\.\d{{1,3}}[A-Za-z]?(?:\s?\([a-z0-9]{{1,3}}\))*)\s+(?P<title>[{UPPER}][^\n]{{1,160}})$"
)
MADDE_RE = re.compile(r"^(?:MADDE|Madde)\s+(?P<num>\d+)(?:\s*[–\-—]\s*|\s+)?(?P<rest>.*)$")
MAJOR_RE = re.compile(
    r"^(?P<kind>APPENDIX|ANNEX|ATTACHMENT|METHOD|CHAPTER|SECTION|SUBPART|PART|EK|BÖLÜM|KISIM)"
    r"[\s\-]+(?P<id>[A-Z0-9IVX]{1,6}(?:\.[0-9]{1,3})?)\b[\s\.:–\-—]*(?P<title>.{0,160})$",
)
TOC_LINE_RE = re.compile(r"(\.{4,}|…{2,}|(\s\.){4,})\s*[\dA-Z\-ivx]{1,6}\s*$")
TRAILING_PAGE_RE = re.compile(r"\s\d{1,4}$")
TOC_TITLE_RE = re.compile(r"^(TABLE OF CONTENTS|CONTENTS|İÇİNDEKİLER|ICINDEKILER|LIST OF (FIGURES|TABLES))\b", re.I)
LIST_START_RE = re.compile(r"^(\(?[a-z0-9]{1,3}\)|[a-z]\.|\d{1,2}\)|[•\-–▪●])\s")


@dataclass
class Line:
    text: str
    page: int
    size: float
    bold: bool
    y0: float
    page_h: float


@dataclass
class Section:
    ref: str
    heading: str
    path: list[str]
    page_start: int
    lines: list[Line] = field(default_factory=list)

    @property
    def page_end(self) -> int:
        return self.lines[-1].page if self.lines else self.page_start


@dataclass
class Chunk:
    ord: int
    clause_ref: str
    heading: str
    heading_path: str
    part: int
    page_start: int
    page_end: int
    content: str

    @property
    def word_count(self) -> int:
        return len(self.content.split())


@dataclass
class ParsedDocument:
    page_count: int
    chunks: list[Chunk]
    structured: bool
    title_guess: str = ""


# ---------------------------------------------------------------------------
# 1) Satırları oku
# ---------------------------------------------------------------------------
def _read_lines(doc: pymupdf.Document) -> list[list[Line]]:
    pages: list[list[Line]] = []
    for pno, page in enumerate(doc, start=1):
        h = page.rect.height or 792
        out: list[Line] = []
        data = page.get_text("dict", sort=True, flags=pymupdf.TEXT_PRESERVE_WHITESPACE | pymupdf.TEXT_MEDIABOX_CLIP)
        for block in data.get("blocks", []):
            if block.get("type") != 0:
                continue
            for ln in block.get("lines", []):
                spans = [s for s in ln.get("spans", []) if s.get("text", "").strip()]
                if not spans:
                    continue
                text = " ".join(" ".join(s["text"].split()) for s in spans).strip()
                text = text.replace(" ", " ").replace("­", "")
                if not text:
                    continue
                sizes = [s.get("size", 10) for s in spans]
                bold = any((s.get("flags", 0) & 16) or "bold" in s.get("font", "").lower() for s in spans[:2])
                out.append(Line(text, pno, round(max(sizes), 1), bool(bold), ln["bbox"][1], h))
        pages.append(_merge_same_row(out))
    return pages


def _merge_same_row(lines: list[Line]) -> list[Line]:
    """Aynı satırda ayrı span bloğu olarak gelen parçaları (ör. "4.3" + "Başlık") birleştir."""
    merged: list[Line] = []
    for ln in lines:
        if merged and abs(merged[-1].y0 - ln.y0) < 1.5 and len(merged[-1].text) < 25:
            prev = merged[-1]
            merged[-1] = Line(f"{prev.text} {ln.text}", prev.page, max(prev.size, ln.size), prev.bold or ln.bold, prev.y0, prev.page_h)
        else:
            merged.append(ln)
    return merged


# ---------------------------------------------------------------------------
# 2) Üst/alt bilgi ve içindekiler temizliği
# ---------------------------------------------------------------------------
def _norm_key(text: str) -> str:
    return re.sub(r"\d+", "#", text.lower()).strip()


def _strip_boilerplate(pages: list[list[Line]]) -> list[list[Line]]:
    n = len(pages)
    if n >= 3:
        counts: Counter[str] = Counter()
        for lines in pages:
            keys = {_norm_key(l.text) for l in lines if l.y0 < l.page_h * 0.1 or l.y0 > l.page_h * 0.88}
            counts.update(keys)
        threshold = max(3, int(n * 0.3))
        repeated = {k for k, c in counts.items() if c >= threshold}
    else:
        repeated = set()

    cleaned: list[list[Line]] = []
    for lines in pages:
        body = []
        for l in lines:
            edge = l.y0 < l.page_h * 0.1 or l.y0 > l.page_h * 0.88
            if edge and _norm_key(l.text) in repeated:
                continue
            if edge and re.fullmatch(r"(page|sayfa)?\s*[\divxlc]+(\s*(/|of|-)\s*\d+)?", l.text.strip(), re.I):
                continue  # salt sayfa numarası
            body.append(l)
        toc_like = sum(1 for l in body if TOC_LINE_RE.search(l.text))
        has_toc_title = any(TOC_TITLE_RE.match(l.text) for l in body[:6])
        trailing_nums = sum(1 for l in body if TRAILING_PAGE_RE.search(l.text) and len(l.text) < 110)
        if body and (toc_like / len(body) > 0.3 or (has_toc_title and trailing_nums / len(body) > 0.35)):
            cleaned.append([])  # içindekiler sayfası
            continue
        cleaned.append([l for l in body if not TOC_LINE_RE.search(l.text)])
    return cleaned


# ---------------------------------------------------------------------------
# 3) Başlık algılama
# ---------------------------------------------------------------------------
def _parts(ref: str) -> list[int] | None:
    ref = re.sub(r"^[A-Z]\.", "", ref).replace("-", ".")
    try:
        return [int(p) for p in ref.split(".") if p != ""]
    except ValueError:
        return None


def _plausible_next(stack: list[int], parts: list[int]) -> bool:
    """Numara bir önceki başlığın çocuğu, kardeşi ya da üst seviye kardeşi mi?"""
    if not stack:
        return len(parts) == 1 and parts[0] <= 3 or parts == [1] * len(parts)
    depth = len(parts)
    if depth == len(stack) + 1:
        return parts[:-1] == stack and parts[-1] in (1, 2)
    if depth <= len(stack):
        prefix = stack[: depth - 1]
        return parts[:-1] == prefix and 1 <= parts[-1] - stack[depth - 1] <= 3
    return False


class HeadingDetector:
    def __init__(self, body_size: float):
        self.body_size = body_size
        self.stack: list[int] = []

    def styled(self, line: Line) -> bool:
        return line.bold or line.size >= self.body_size + 0.8

    def reset(self) -> None:
        self.stack = []

    def detect(self, line: Line, prev_text: str | None) -> tuple[str, str, str] | None:
        """Başlıksa (tür, ref, başlık) döner. tür: major | dec | cfr | easa | madde"""
        t = line.text.strip()
        if len(t) > 190:
            return None

        m = MAJOR_RE.match(t)
        if m and (self.styled(line) or t.isupper() or len(t) < 60):
            kind = m.group("kind").upper()
            title = m.group("title").strip(" .:-–—")
            # "PART 25" gibi metin içi atıfları değil, bağımsız satırları al
            if kind in {"SECTION", "PART"} and not (self.styled(line) or t.isupper()):
                return None
            return "major", f"{kind.title()} {m.group('id')}", title

        m = DASH_RE.match(t)
        if m and (self.styled(line) or m.group("title").split(".")[0].isupper()):
            parts = [int(x) for x in m.group("ref").split("-")]
            # "3-1" yeni bölümün ilk paragrafıdır; aksi halde sıra tutarlılığı aranır
            if _plausible_next(self.stack, parts) or parts[1] in (1, 2) or self.styled(line):
                self.stack = parts
                head = re.split(r"(?<=[A-Za-z\)])\.\s", m.group("title"), maxsplit=1)[0]
                return "dec", m.group("ref"), head.rstrip(" .")[:150]

        m = CFR_RE.match(t)
        if m:
            return "cfr", f"§ {m.group('ref')}", m.group("title").strip().rstrip(".")

        m = EASA_RE.match(t)
        if m and (self.styled(line) or len(t) < 120):
            return "easa", " ".join(m.group("ref").split()), m.group("title").strip().rstrip(".")

        m = MADDE_RE.match(t)
        if m:
            heading = ""
            if prev_text and len(prev_text) < 70 and not prev_text.rstrip().endswith((".", ",", ";", ":")):
                heading = prev_text.strip()
            return "madde", f"Madde {m.group('num')}", heading

        m = DEC_RE.match(t)
        if not m:
            return None
        title = m.group("title").strip()
        ref = m.group("ref")
        parts = _parts(ref)
        if not parts or any(p > 199 for p in parts):
            return None
        if TRAILING_PAGE_RE.search(t) and len(title.split()) > 1 and not self.styled(line):
            # "4.3 Hazard analysis 12" — içindekiler satırı olabilir
            return None
        words = title.split()
        looks_title = (
            self.styled(line)
            or title.isupper()
            or (len(words) <= 14 and not title.rstrip().endswith((",", ";")))
            or len(parts) >= 2
        )
        if not looks_title:
            return None
        if len(parts) == 1 and not (self.styled(line) or title.isupper() or m.group("dot")):
            return None  # "3 hours of exposure" gibi gövde satırlarını eleme
        plausible = _plausible_next(self.stack, parts)
        if plausible or (self.styled(line) and (parts[-1] <= 2 or len(parts) == 1)):
            self.stack = parts
            # Başlık + gövde aynı satırdaysa ("4.3.1 General. The contractor shall...") başlığı kırp
            head = re.split(r"(?<=[a-z\)])\.\s", title, maxsplit=1)[0]
            return "dec", ref, head[:150].rstrip(" .")
        return None


# ---------------------------------------------------------------------------
# 4) Metin birleştirme ve bölme
# ---------------------------------------------------------------------------
def _join_lines(lines: list[Line]) -> str:
    out = ""
    for ln in lines:
        t = ln.text
        if not out:
            out = t
            continue
        if out.endswith("-") and t[:1].islower():
            out = out[:-1] + t
        elif LIST_START_RE.match(t) or out.endswith((".", ":", ";")) and t[:1].isupper():
            out += "\n" + t
        else:
            out += " " + t
    out = re.sub(r"[ \t]+", " ", out)
    return out.strip()


def _split_long(text: str) -> list[str]:
    words = text.split()
    if len(words) <= MAX_WORDS:
        return [text]
    paras = [p for p in text.split("\n") if p.strip()]
    pieces: list[str] = []
    cur: list[str] = []
    cur_words = 0
    for p in paras:
        pw = len(p.split())
        if pw > MAX_WORDS:  # tek dev paragraf: kelime penceresiyle böl
            if cur:
                pieces.append("\n".join(cur))
                cur, cur_words = [], 0
            ws = p.split()
            step = MAX_WORDS - OVERLAP_WORDS
            for i in range(0, len(ws), step):
                pieces.append(" ".join(ws[i : i + MAX_WORDS]))
                if i + MAX_WORDS >= len(ws):
                    break
            continue
        if cur_words + pw > MAX_WORDS and cur:
            pieces.append("\n".join(cur))
            tail = " ".join(" ".join(cur).split()[-OVERLAP_WORDS:])
            cur, cur_words = [f"… {tail}"], OVERLAP_WORDS
        cur.append(p)
        cur_words += pw
    if cur:
        pieces.append("\n".join(cur))
    return pieces


def _page_of_piece(sec: Section, piece_idx: int, n_pieces: int) -> tuple[int, int]:
    if n_pieces == 1:
        return sec.page_start, sec.page_end
    pages = [l.page for l in sec.lines] or [sec.page_start]
    a = pages[int(len(pages) * piece_idx / n_pieces)]
    b = pages[min(len(pages) - 1, int(len(pages) * (piece_idx + 1) / n_pieces))]
    return a, max(a, b)


# ---------------------------------------------------------------------------
# 5) Ana akış
# ---------------------------------------------------------------------------
def parse_pdf(path: str | Path) -> ParsedDocument:
    with pymupdf.open(str(path)) as doc:
        page_count = doc.page_count
        raw_pages = _read_lines(doc)
        title_guess = (doc.metadata or {}).get("title", "") or ""

    pages = _strip_boilerplate(raw_pages)
    all_lines = [l for p in pages for l in p]
    if not all_lines:
        raise ValueError("PDF'te metin bulunamadı (taranmış görüntü olabilir; OCR gerekli).")

    sizes = [l.size for l in all_lines if len(l.text) > 30] or [l.size for l in all_lines]
    body_size = statistics.mode(sizes)
    det = HeadingDetector(body_size)

    sections: list[Section] = [Section("", "Ön bölüm", [], all_lines[0].page)]
    major_title = ""
    level_titles: dict[int, str] = {}
    prev_text: str | None = None

    for ln in all_lines:
        found = det.detect(ln, prev_text)
        if found:
            kind, ref, heading = found
            if kind == "major":
                det.reset()
                level_titles.clear()
                major_title = f"{ref} {heading}".strip()
                path = [major_title]
            elif kind == "dec":
                depth = len(_parts(ref) or [1])
                level_titles = {d: t for d, t in level_titles.items() if d < depth}
                level_titles[depth] = f"{ref} {heading}".strip()
                path = ([major_title] if major_title else []) + [level_titles[d] for d in sorted(level_titles)]
            elif kind == "madde":
                # Önceki satır başlık olarak kullanıldıysa onu önceki maddeden çıkar
                if heading and sections[-1].lines and sections[-1].lines[-1].text.strip() == heading:
                    sections[-1].lines.pop()
                path = ([major_title] if major_title else []) + [f"{ref} {heading}".strip()]
                rest = MADDE_RE.match(ln.text.strip()).group("rest")
                sections.append(Section(ref, heading, path, ln.page))
                if rest:
                    sections[-1].lines.append(Line(rest, ln.page, ln.size, False, ln.y0, ln.page_h))
                prev_text = ln.text
                continue
            else:
                path = ([major_title] if major_title else []) + [f"{ref} {heading}".strip()]
            sections.append(Section(ref, heading, path, ln.page))
            # Başlık satırında gövde de varsa (ör. "4.3.1 General. The contractor shall ...") gövdeye ekle
            rest = ln.text.strip()
            title_part = f"{ref} {heading}".strip()
            if kind == "dec" and len(rest) > len(title_part) + 15:
                remainder = rest.split(heading, 1)[-1].lstrip(" .")
                if remainder:
                    sections[-1].lines.append(Line(remainder, ln.page, ln.size, False, ln.y0, ln.page_h))
        else:
            sections[-1].lines.append(ln)
        prev_text = ln.text

    structured = sum(1 for s in sections if s.ref) >= max(3, page_count // 15)
    if not structured:
        return ParsedDocument(page_count, _page_window_chunks(pages), False, title_guess)

    chunks: list[Chunk] = []
    for sec in sections:
        body = _join_lines(sec.lines)
        if len(body.split()) < MIN_BODY_WORDS:
            continue
        pieces = _split_long(body)
        for i, piece in enumerate(pieces):
            ps, pe = _page_of_piece(sec, i, len(pieces))
            chunks.append(
                Chunk(
                    ord=len(chunks),
                    clause_ref=sec.ref,
                    heading=sec.heading[:200],
                    heading_path=" › ".join(sec.path)[:600],
                    part=i + 1,
                    page_start=ps,
                    page_end=pe,
                    content=piece,
                )
            )
    if not chunks:
        return ParsedDocument(page_count, _page_window_chunks(pages), False, title_guess)
    return ParsedDocument(page_count, chunks, True, title_guess)


def _page_window_chunks(pages: list[list[Line]]) -> list[Chunk]:
    """Yapı bulunamazsa: sayfaları sırayla birleştirip kelime penceresiyle böl."""
    chunks: list[Chunk] = []
    buf: list[Line] = []
    for lines in pages:
        buf.extend(lines)
        text = _join_lines(buf)
        if len(text.split()) >= MAX_WORDS:
            chunks.append(_window_chunk(len(chunks), buf, text))
            buf = []
    if buf:
        text = _join_lines(buf)
        if len(text.split()) >= MIN_BODY_WORDS:
            chunks.append(_window_chunk(len(chunks), buf, text))
    return chunks


def _window_chunk(ord_: int, buf: list[Line], text: str) -> Chunk:
    ps, pe = buf[0].page, buf[-1].page
    ref = f"s. {ps}" if ps == pe else f"s. {ps}-{pe}"
    return Chunk(ord_, ref, "", ref, 1, ps, pe, text)
