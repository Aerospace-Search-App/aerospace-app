"""Sunum PDF'i için Swagger ekran görüntülerini üretir (uygulama kodu değil, araç script'i).

Ne yapar:
1. API sunucusunu kendisi başlatır (`uvicorn main:app --port 8000`), `/health` hazır olana kadar bekler.
2. Sistemdeki Edge (olmazsa Chrome) ile Swagger'ı (`/docs`) açar; her adımda ilgili operasyonu açar →
   "Try it out" → gövde/parametre girer → "Execute" → yalnızca o operasyon bloğunun görüntüsünü alır.
3. İş bitince (hata olsa bile) sunucuyu kapatır.

Veri bellek-içi olduğu için adımların sırası önemlidir (önce standart ekle, sonra aynı kodla 409 vb.).
Her çalıştırmada sunucu sıfırdan başladığından script tekrar tekrar çalıştırılabilir.

Çalıştırma: `.venv/Scripts/python tools/screenshots.py`  (port doluysa: `... tools/screenshots.py --port 8001`)
Çıktı:      `docs/rapor/img/NN_ad.png`
"""

import argparse
import json
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

from loguru import logger
from playwright.sync_api import Browser, Locator, Page, Playwright, sync_playwright

ROOT = Path(__file__).resolve().parent.parent
IMG_DIR = ROOT / "docs" / "rapor" / "img"
HOST = "127.0.0.1"
PORT = 8000  # --port ile değiştirilebilir (main() içinde)
BASE_URL = f"http://localhost:{PORT}"
SERVER_START_TIMEOUT_S = 30

# Görüntüleri sadeleştiren CSS (sadece görünüm; istek/cevap değişmez): curl komutu, cevap HTTP başlıkları,
# kopyala/indir butonları ve belgelenmiş (statik) cevap tablosu gizlenir; canlı cevap gövdesinin yükseklik
# sınırı kaldırılır ki JSON kesilmesin. Request URL, status kodu ve JSON gövde görünür kalır.
CLEANUP_CSS = """
.opblock .curl-command { display: none !important; }
.opblock .responses-inner > table.responses-table:not(.live-responses-table) { display: none !important; }
.opblock .responses-inner > div > h4 { display: none !important; }
.opblock .live-responses-table .response-col_description > div:has(.headerline) { display: none !important; }
.opblock .live-responses-table .download-contents,
.opblock .live-responses-table .copy-to-clipboard { display: none !important; }
.opblock .microlight, .opblock .highlight-code pre { max-height: none !important; overflow: visible !important; }
"""

# PDF için sıkıştırılmış görünüm: A4'e sığarken JSON okunur kalsın diye operasyon açıklaması, bölüm başlık
# çubukları, parametre açıklamaları, "Edit Value | Schema" sekmeleri ve Execute/Clear satırı gizlenir; JSON ve
# status kodu yazısı büyütülür. Görünür kalan: yöntem + adres çubuğu, girilen parametre/gövde, Request URL,
# status kodu ve cevap gövdesi. Kurallar sadece `shot` sınıfı eklenen blokta, görüntü alınırken geçerlidir
# (Execute butonu tıklanırken görünür olmalı).
COMPACT_CSS = """
.opblock.shot .opblock-body > .opblock-description-wrapper,
.opblock.shot .responses-inner > div > div > h4,
.opblock.shot .opblock-section > .opblock-section-header,
.opblock.shot .parameters-container .opblock-description-wrapper,
.opblock.shot table.parameters thead,
.opblock.shot .parameter__type, .opblock.shot .parameter__deprecated, .opblock.shot .parameter__in,
.opblock.shot .parameters-col_description .markdown, .opblock.shot .parameters-col_description .renderedMarkdown,
.opblock.shot .parameter__extension, .opblock.shot .parameter__enum,
.opblock.shot .opblock-section-request-body ul.tab,
.opblock.shot .btn-group,
.opblock.shot .responses-wrapper > .opblock-section-header,
.opblock.shot .live-responses-table thead,
.opblock.shot .live-responses-table .response-col_description > div > h5 { display: none !important; }
.opblock.shot .opblock-section-request-body .opblock-description-wrapper { padding: 4px 20px !important; }
.opblock.shot .table-container { padding: 6px 20px !important; }
.opblock.shot table.parameters td { padding: 4px 0 !important; }
.opblock.shot table.parameters input, .opblock.shot table.parameters select { margin: 0 !important; }
.opblock.shot .responses-inner { padding-top: 8px !important; }
.opblock.shot .live-responses-table .microlight { font-size: 15px !important; line-height: 1.35 !important; }
.opblock.shot .request-url .microlight, .opblock.shot .body-param__text { font-size: 14px !important; }
.opblock.shot .live-responses-table .response-col_status { font-size: 17px !important; font-weight: 700 !important; width: 46px !important; min-width: 0 !important; padding-right: 6px !important; }
"""
OVERVIEW_WIDTH = 900    # 01: başlık + Authorize + gruplar; dar viewport → PDF'te okunur yazı
OPERATION_WIDTH = 560   # 02–12: dar viewport → PDF'te iki sütunda okunur yazı

NEW_STANDARD = {
    "code": "RTCA-DO-160G",
    "title": "Environmental Conditions and Test Procedures for Airborne Equipment",
    "standard_type": "CIVIL",
    "version": "G",
    "issuing_body": "RTCA",
    "publication_year": 2010,
}


# --------------------------------------------------------------------------- sunucu yönetimi
def _port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        return sock.connect_ex((HOST, port)) == 0


def start_server() -> subprocess.Popen[bytes]:
    """Sunucuyu alt süreç olarak başlatır. Port doluysa başka süreci öldürmez, açık hata verir."""
    if _port_in_use(PORT):
        raise RuntimeError(f"{PORT} portu dolu. Çalışan sunucuyu kapatıp script'i tekrar çalıştırın.")
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "main:app", "--host", HOST, "--port", str(PORT)],
        cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    deadline = time.monotonic() + SERVER_START_TIMEOUT_S
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            raise RuntimeError(f"Sunucu başlarken kapandı (çıkış kodu {proc.returncode}).")
        try:
            with urllib.request.urlopen(f"{BASE_URL}/health", timeout=1) as resp:
                if resp.status == 200:
                    logger.info("Sunucu hazır: {}", BASE_URL)
                    return proc
        except OSError:
            time.sleep(0.3)
    stop_server(proc)
    raise RuntimeError("Sunucu zamanında hazır olmadı.")


def stop_server(proc: subprocess.Popen[bytes]) -> None:
    proc.terminate()
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=5)
    logger.info("Sunucu durduruldu.")


# --------------------------------------------------------------------------- yardımcılar
def make_minimal_pdf(path: Path) -> Path:
    """`%PDF-1.4` ile başlayan, tek sayfalık geçerli bir PDF üretir (xref ofsetleri hesaplanır)."""
    stream = b"BT /F1 18 Tf 72 720 Td (RTCA DO-160G - Demo) Tj ET"
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R "
        b"/Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{number} 0 obj\n".encode() + body + b"\nendobj\n"
    xref_pos = len(out)
    out += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
    for offset in offsets:
        out += f"{offset:010d} 00000 n \n".encode()
    out += f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_pos}\n%%EOF\n".encode()
    path.write_bytes(bytes(out))
    return path


def launch_browser(p: Playwright) -> Browser:
    for channel in ("msedge", "chrome"):
        try:
            browser = p.chromium.launch(channel=channel)
            logger.info("Tarayıcı: {}", channel)
            return browser
        except Exception as exc:  # noqa: BLE001 — sıradaki kanalı denemek için
            logger.warning("{} açılamadı: {}", channel, exc)
    raise RuntimeError("Sistemde Edge veya Chrome bulunamadı.")


def open_swagger(page: Page) -> None:
    page.goto(f"{BASE_URL}/docs")
    page.wait_for_selector(".opblock-tag-section", timeout=30_000)
    page.add_style_tag(content=CLEANUP_CSS + COMPACT_CSS)


def operation(page: Page, method: str, path: str) -> Locator:
    return page.locator(
        f"div.opblock.opblock-{method}:has(.opblock-summary-path[data-path='{path}'])"
    ).first


def expand(op: Locator) -> None:
    if "is-open" not in (op.get_attribute("class") or ""):
        op.locator(".opblock-summary").first.click()
    op.locator(".opblock-body").wait_for()
    try_out = op.locator("button.try-out__btn").first
    try_out.wait_for()
    if try_out.inner_text().strip().lower().startswith("try"):  # "Cancel" ise zaten açık
        try_out.click()
    op.locator("button.execute").wait_for()


def set_body(op: Locator, body: dict[str, object]) -> None:
    area = op.locator("textarea.body-param__text")
    area.fill(json.dumps(body, ensure_ascii=False, indent=2))
    # Kutuyu içeriğe göre kısalt (Swagger'ın varsayılan boş alanı görüntüyü gereksiz uzatıyor).
    area.evaluate("e => { e.style.minHeight = '0'; e.style.height = 'auto'; e.style.height = (e.scrollHeight + 8) + 'px'; }")


def set_param(op: Locator, name: str, value: str) -> None:
    field = op.locator(f"tr[data-param-name='{name}'] input").first
    field.fill(value)


def execute(op: Locator) -> str:
    """Execute'a basar, canlı cevap gelene kadar bekler ve cevap gövdesini (metin) döner."""
    live = op.locator(".live-responses-table")
    clear = op.locator("button.btn-clear")
    if clear.count():  # aynı operasyon tekrar çalıştırılıyorsa eski cevabı temizle
        clear.first.click()
        live.wait_for(state="detached")
    op.locator("button.execute").click()
    live.wait_for(timeout=15_000)
    op.locator(".live-responses-table .response-col_status").first.wait_for()
    page = op.page
    page.wait_for_timeout(400)  # microlight renklendirmesi bitsin
    return op.locator(".live-responses-table .response-col_description pre").first.inner_text()


def live_status(op: Locator) -> str:
    return op.locator(".live-responses-table tbody .response-col_status").first.inner_text().strip()


def shoot(op: Locator, name: str) -> None:
    target = IMG_DIR / name
    op.evaluate("e => e.classList.add('shot')")
    op.scroll_into_view_if_needed()
    op.screenshot(path=str(target))
    box = op.bounding_box() or {"width": 0, "height": 0}
    op.evaluate("e => e.classList.remove('shot')")
    logger.info("{} kaydedildi (status {}) ~{}x{} css px, x2 ölçek",
                name, live_status(op), int(box["width"]), int(box["height"]))


def run_operation(page: Page, method: str, path: str, name: str, *, body: dict[str, object] | None = None,
                  params: dict[str, str] | None = None, file: Path | None = None,
                  hide_params: tuple[str, ...] = ()) -> str:
    """Bir operasyonu uçtan uca çalıştırıp görüntüsünü alır; cevap gövdesini (metin) döner.

    `hide_params`: görüntüyü kısaltmak için boş bırakılan opsiyonel filtre satırlarını gizler (sadece görünüm).
    """
    op = operation(page, method, path)
    expand(op)
    for name_ in hide_params:
        op.locator(f"tr[data-param-name='{name_}']").evaluate("e => e.style.display = 'none'")
    for key, value in (params or {}).items():
        set_param(op, key, value)
    if body is not None:
        set_body(op, body)
    if file is not None:
        op.locator("input[type=file]").set_input_files(str(file))
    text = execute(op)
    shoot(op, name)
    return text


def collapse_operation(page: Page, method: str, path: str) -> None:
    op = operation(page, method, path)
    if "is-open" in (op.get_attribute("class") or ""):
        op.locator(".opblock-summary").first.click()


# --------------------------------------------------------------------------- akış
def shoot_overview(page: Page) -> None:
    """01: Başlık + Authorize + tüm gruplar kapalı. Uzun API açıklama paragrafı (PDF'te okunmayacak kadar küçük
    kalıyordu) bu görüntüde gizlenir; sayfa sonra yeniden yüklendiği için diğer adımları etkilemez."""
    page.add_style_tag(content=".swagger-ui .information-container .info .description { display: none !important; }"
                               " .swagger-ui .information-container .info { margin: 24px 0 !important; }")
    for tag in page.locator("h3.opblock-tag").all():
        if tag.get_attribute("data-is-open") == "true":
            tag.click()
    page.mouse.move(0, 0)  # son tıklanan grupta hover gölgesi kalmasın
    page.wait_for_timeout(400)
    last = page.locator(".opblock-tag-section").last.bounding_box()
    assert last is not None
    height = int(last["y"] + last["height"] + 24)
    page.screenshot(path=str(IMG_DIR / "01_swagger_genel.png"),
                    clip={"x": 0, "y": 0, "width": OVERVIEW_WIDTH, "height": height}, full_page=True)
    logger.info("01_swagger_genel.png kaydedildi ~{}x{} css px, x2 ölçek", OVERVIEW_WIDTH, height)


def run_flow(page: Page, pdf_path: Path) -> None:
    open_swagger(page)
    shoot_overview(page)

    page.set_viewport_size({"width": OPERATION_WIDTH, "height": 1000})
    open_swagger(page)  # temiz sayfa: gruplar varsayılan (açık) halde
    run_operation(page, "get", "/health", "02_health.png")
    run_operation(page, "get", "/api/v1/standards", "03_standart_liste.png", params={"page_size": "1"},
                  hide_params=("q", "standard_type", "status", "index_status"))
    created = json.loads(run_operation(page, "post", "/api/v1/standards", "04_standart_ekle_201.png",
                                       body=NEW_STANDARD))
    new_id = str(created["id"])
    logger.info("Yeni standart id: {}", new_id)

    run_operation(page, "post", "/api/v1/standards", "05_hata_409.png",
                  body={**NEW_STANDARD, "code": NEW_STANDARD["code"].lower()})
    collapse_operation(page, "post", "/api/v1/standards")

    run_operation(page, "post", "/api/v1/standards/{standard_id}/document", "06_pdf_yukle_202.png",
                  params={"standard_id": new_id}, file=pdf_path)

    status_path = "/api/v1/standards/{standard_id}/index-status"
    for attempt in range(5):
        text = run_operation(page, "get", status_path, "07_index_status.png", params={"standard_id": new_id})
        if '"INDEXED"' in text:
            break
        logger.info("Henüz INDEXED değil (deneme {}), bekleniyor...", attempt + 1)
        page.wait_for_timeout(1000)

    run_operation(page, "post", "/api/v1/chat/ask", "08_chat_ask.png",
                  body={"question": "Vibrasyon testi kaç saat sürmeli?", "standard_ids": [1], "top_k": 2})
    run_operation(page, "post", "/api/v1/reports/{report_id}/analyses", "09_rapor_analiz_201.png",
                  params={"report_id": "1"},
                  body={"query": "Rapor vibrasyon gereksinimlerini karşılıyor mu?", "standard_ids": [1], "top_k": 2})
    run_operation(page, "post", "/api/v1/chat/ask", "10_hata_422.png", body={"question": "ab"})
    collapse_operation(page, "post", "/api/v1/chat/ask")
    run_operation(page, "get", "/api/v1/chat/conversations", "11_sohbet_gecmisi.png")
    run_operation(page, "post", "/auth/login", "12_auth_login.png",
                  body={"email": "demo@aerospace.local", "password": "demo12345"})


def main() -> None:
    global PORT, BASE_URL
    parser = argparse.ArgumentParser(description="Swagger ekran görüntülerini üretir.")
    parser.add_argument("--port", type=int, default=PORT, help="Script'in başlatacağı sunucunun portu.")
    PORT = parser.parse_args().port
    BASE_URL = f"http://localhost:{PORT}"
    IMG_DIR.mkdir(parents=True, exist_ok=True)
    server = start_server()
    try:
        with tempfile.TemporaryDirectory() as tmp, sync_playwright() as p:
            pdf_path = make_minimal_pdf(Path(tmp) / "do160g_demo.pdf")
            browser = launch_browser(p)
            try:
                context = browser.new_context(viewport={"width": OVERVIEW_WIDTH, "height": 1000}, device_scale_factor=2,
                                              locale="tr-TR")
                run_flow(context.new_page(), pdf_path)
            finally:
                browser.close()
    finally:
        stop_server(server)
    logger.info("Bitti: {} dosya → {}", len(list(IMG_DIR.glob("*.png"))), IMG_DIR)


if __name__ == "__main__":
    main()
