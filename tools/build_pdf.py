"""Sunum PDF'ini üretir: `docs/rapor/rapor.html` → `docs/rapor/Kagan_Bayrak_API_Iskeleti.pdf` (+ masaüstü kopyası).

Ne yapar:
- Sistemdeki Edge'i (olmazsa Chrome) Playwright ile açar; tarayıcı indirmez, sunucu gerektirmez.
- Sayfa boyutu, kenar boşlukları ve altbilgi (sayfa no + "API İskeleti · Kağan Bayrak") HTML içindeki CSS `@page`
  kurallarından gelir (`prefer_css_page_size=True`); kapakta altbilgi yoktur (`@page :first`).
- Sayfa sayısını PDF baytlarındaki `/Type /Page` nesnelerinden sayıp yazdırır (ek kütüphane gerekmez).

Çalıştırma: `.venv/Scripts/python tools/build_pdf.py`
Ekran görüntüleri önce `tools/screenshots.py` ile üretilmiş olmalı (`docs/rapor/img/`).
"""

import re
import shutil
from pathlib import Path

from loguru import logger
from playwright.sync_api import Browser, Playwright, sync_playwright

ROOT = Path(__file__).resolve().parent.parent
HTML = ROOT / "docs" / "rapor" / "rapor.html"
PDF = ROOT / "docs" / "rapor" / "Kagan_Bayrak_API_Iskeleti.pdf"
DESKTOP_COPY = Path.home() / "Desktop" / PDF.name

# "/Type /Page" eşleşsin ama "/Type /Pages" eşleşmesin.
_PAGE_OBJECT = re.compile(rb"/Type\s*/Page(?![a-zA-Z])")


def launch_browser(p: Playwright) -> Browser:
    for channel in ("msedge", "chrome"):
        try:
            browser = p.chromium.launch(channel=channel)
            logger.info("Tarayıcı: {} {}", channel, browser.version)
            return browser
        except Exception as exc:  # noqa: BLE001 — sıradaki kanalı denemek için
            logger.warning("{} açılamadı: {}", channel, exc)
    raise RuntimeError("Sistemde Edge veya Chrome bulunamadı.")


def build() -> int:
    """PDF'i üretir, masaüstü varsa oraya kopyalar ve sayfa sayısını döner."""
    missing = [img for img in re.findall(r'src="(img/[^"]+)"', HTML.read_text(encoding="utf-8"))
               if not (HTML.parent / img).exists()]
    if missing:
        raise FileNotFoundError(f"Eksik görsel(ler): {missing}. Önce tools/screenshots.py çalıştırın.")

    with sync_playwright() as p:
        browser = launch_browser(p)
        try:
            page = browser.new_page()
            page.goto(HTML.as_uri(), wait_until="networkidle")
            data = page.pdf(prefer_css_page_size=True, print_background=True)
        finally:
            browser.close()

    PDF.write_bytes(data)
    pages = len(_PAGE_OBJECT.findall(data))
    logger.info("PDF yazıldı: {} ({} sayfa, {:.0f} KB)", PDF, pages, len(data) / 1024)
    if DESKTOP_COPY.parent.is_dir():
        shutil.copyfile(PDF, DESKTOP_COPY)
        logger.info("Masaüstü kopyası: {}", DESKTOP_COPY)
    else:
        logger.info("Masaüstü klasörü yok, kopya atlandı: {}", DESKTOP_COPY.parent)
    return pages


if __name__ == "__main__":
    build()
