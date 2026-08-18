from pathlib import Path

from playwright.sync_api import sync_playwright


presentation_dir = Path(__file__).resolve().parent
html_path = presentation_dir / "2026-08-17-ai4ls-final.html"
pdf_path = presentation_dir / "2026-08-17-ai4ls-final.pdf"

with sync_playwright() as playwright:
    browser = playwright.chromium.launch()
    page = browser.new_page(viewport={"width": 1920, "height": 1080})
    page.goto(html_path.as_uri(), wait_until="load")
    page.wait_for_timeout(2_000)
    page.emulate_media(media="print")
    page.pdf(
        path=str(pdf_path),
        print_background=True,
        prefer_css_page_size=True,
    )
    browser.close()

print(pdf_path)
