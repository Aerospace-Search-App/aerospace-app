"""Testler için gerçek standart düzenini taklit eden örnek PDF'ler üretir (reportlab gerekir)."""
from __future__ import annotations

from pathlib import Path

from reportlab.lib.pagesizes import letter
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

LOREM = (
    "The applicant should establish and document the processes used to satisfy the objectives. "
    "Each requirement shall be verified by analysis, inspection, demonstration or test, and the "
    "verification results shall be retained as part of the certification evidence. "
)


def _font():
    for p in ["/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "C:/Windows/Fonts/arial.ttf"]:
        if Path(p).exists():
            pdfmetrics.registerFont(TTFont("U", p))
            bold = p.replace("DejaVuSans.ttf", "DejaVuSans-Bold.ttf").replace("arial.ttf", "arialbd.ttf")
            pdfmetrics.registerFont(TTFont("UB", bold if Path(bold).exists() else p))
            return "U", "UB"
    return "Helvetica", "Helvetica-Bold"


class Writer:
    def __init__(self, path: Path, header: str):
        self.c = canvas.Canvas(str(path), pagesize=letter)
        self.header = header
        self.page = 1
        self.y = 720
        self.reg, self.bold = _font()
        self._decorate()

    def _decorate(self):
        self.c.setFont(self.reg, 8)
        self.c.drawString(72, 760, self.header)
        self.c.drawString(300, 30, str(self.page))

    def new_page(self):
        self.c.showPage()
        self.page += 1
        self.y = 720
        self._decorate()

    def line(self, text: str, bold=False, size=10):
        if self.y < 60:
            self.new_page()
        self.c.setFont(self.bold if bold else self.reg, size)
        self.c.drawString(72, self.y, text)
        self.y -= size + 4

    def para(self, text: str, width=95):
        words, cur = text.split(), ""
        for w in words:
            if len(cur) + len(w) + 1 > width:
                self.line(cur)
                cur = w
            else:
                cur = f"{cur} {w}".strip()
        if cur:
            self.line(cur)
        self.y -= 4

    def save(self):
        self.c.save()


def make_milstd(path: Path) -> Path:
    w = Writer(path, "MIL-STD-999X")
    w.line("MIL-STD-999X", bold=True, size=16)
    w.line("DEPARTMENT OF DEFENSE STANDARD PRACTICE: SYSTEM SAFETY TEST", bold=True, size=12)
    w.new_page()
    w.line("TABLE OF CONTENTS", bold=True, size=12)
    for ref, t, p in [("1.", "SCOPE", 3), ("1.1", "Purpose", 3), ("2.", "APPLICABLE DOCUMENTS", 3),
                      ("4.", "GENERAL REQUIREMENTS", 4), ("4.1", "Hazard analysis", 4), ("4.2", "Risk assessment", 5)]:
        w.line(f"{ref} {t} " + "." * 40 + f" {p}")
    w.new_page()
    w.line("1. SCOPE", bold=True, size=11)
    w.line("1.1 Purpose.", bold=True)
    w.para("This standard addresses an approach for the management of environment, safety and occupational health mishap risks. " + LOREM)
    w.line("1.2 Application.", bold=True)
    w.para("The system safety requirements apply to all developmental and sustaining engineering activities. " + LOREM)
    w.line("2. APPLICABLE DOCUMENTS", bold=True, size=11)
    w.para("The documents listed in this section are specified in sections 3 and 4 of this standard. " + LOREM)
    w.line("3 hours of exposure is the minimum duration for the humidity cycle in this example sentence that wraps.")
    w.para(LOREM)
    w.line("4. GENERAL REQUIREMENTS", bold=True, size=11)
    w.line("4.1 Hazard analysis.", bold=True)
    w.para("The program manager shall identify hazards through a systematic hazard analysis process. " + LOREM * 2)
    w.line("4.1.1 Hazard tracking system.", bold=True)
    w.para("A closed-loop hazard tracking system shall be established. " + LOREM * 14)
    w.line("4.2 Risk assessment.", bold=True)
    w.para("Assess the severity and probability of the mishap risk associated with each hazard. " + LOREM)
    w.new_page()
    w.line("APPENDIX A", bold=True, size=12)
    w.line("A.1 GUIDANCE ON SEVERITY CATEGORIES", bold=True)
    w.para("Catastrophic severity could result in death, permanent total disability or irreversible significant environmental impact. " + LOREM)
    w.save()
    return path


def make_shgm(path: Path) -> Path:
    w = Writer(path, "SHT-999 Rev.02")
    w.line("ONAYLI HAVA ARACI BAKIM KURULUŞLARI TALİMATI (SHT-999)", bold=True, size=13)
    w.line("BİRİNCİ BÖLÜM", bold=True)
    w.line("Amaç, Kapsam, Dayanak ve Tanımlar", bold=True)
    w.line("Amaç", bold=True)
    w.para("MADDE 1 – (1) Bu Talimatın amacı, hava aracı bakım kuruluşlarının onaylanmasına ilişkin usul ve esasları belirlemektir. "
           "Bakım kuruluşu yeterli personel, tesis ve ekipmana sahip olmalıdır.")
    w.line("Kapsam", bold=True)
    w.para("MADDE 2 – (1) Bu Talimat, Türk sivil hava aracı siciline kayıtlı hava araçlarına bakım hizmeti veren kuruluşları kapsar. "
           "Yabancı kuruluşlar için ayrıca değerlendirme yapılır.")
    w.line("Personel gereklilikleri", bold=True)
    w.para("MADDE 3 – (1) Kuruluş, sorumlu müdür ile kalite müdürünü atar ve bu kişilerin yetkinliğini belgeler. "
           "(2) Sertifikalandırma personeli, ilgili lisans ve tip eğitimlerine sahip olmalıdır. " + LOREM)
    w.save()
    return path


def make_easa(path: Path) -> Path:
    w = Writer(path, "Easy Access Rules for Part-145")
    w.line("SECTION A — TECHNICAL REQUIREMENTS", bold=True, size=12)
    w.line("145.A.25 Facility requirements", bold=True)
    w.para("The organisation shall ensure that facilities are provided appropriate for all planned work. " + LOREM)
    w.line("145.A.30 Personnel requirements", bold=True)
    w.para("The organisation shall appoint an accountable manager who has corporate authority. " + LOREM)
    w.line("AMC1 145.A.30(e) Personnel requirements", bold=True)
    w.para("Competence must be established by assessment of each person against the job description. " + LOREM)
    w.save()
    return path


def make_unstructured(path: Path) -> Path:
    w = Writer(path, "Bulletin")
    for _ in range(6):
        w.para(LOREM * 4)
    w.save()
    return path


def make_faa_ac(path: Path) -> Path:
    """FAA AC düzenleri: "1. Purpose of this AC." ve eski "CHAPTER 1" + "1-1. PURPOSE." numaralandırması."""
    w = Writer(path, "AC 99-1X 7/21/17")
    w.line("Advisory Circular", bold=True, size=14)
    w.line("1. Purpose of this Advisory Circular (AC).", bold=True)
    w.para("This AC describes an acceptable means for showing compliance with airworthiness regulations for software. " + LOREM)
    w.para("a. Applicability of the guidance in this paragraph is limited to new development programs only.")
    w.line("2. Applicability.", bold=True)
    w.para("This AC applies to applicants, design approval holders and developers of airborne systems. " + LOREM)
    w.line("CHAPTER 3. TOOL QUALIFICATION", bold=True, size=12)
    w.line("3-1. GENERAL. Tool qualification is required when the output of a tool is not verified.", bold=False)
    w.para(LOREM)
    w.line("3-2. CRITERIA. The applicant should determine the tool qualification level (TQL).")
    w.para(LOREM)
    w.save()
    return path
