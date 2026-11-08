"""OCR: скан-PDF без текстового слоя и фото документа превращаются в текст с меткой «(OCR)».

Нужны языковые данные Tesseract (rus, eng): в Docker-образе они есть; локально —
apt install tesseract-ocr-rus tesseract-ocr-eng, иначе тесты пропускаются.

    pytest -q tests/test_ocr.py
"""
from pathlib import Path

import pymupdf
import pytest

from tools.doc_text import file_text, ocr_ready

DEMO = Path(__file__).resolve().parent.parent / "demo" / "agrosensor"


def _tessdata() -> bool:
    try:
        return bool(pymupdf.get_tessdata())
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _tessdata(), reason="нет языковых данных Tesseract")


def _pages_as_images(tmp_path: Path) -> list[bytes]:
    """Демо-презентация, отрисованная в серые картинки 150 dpi, — как после сканера."""
    if not (DEMO / "presentation.pdf").exists():
        from demo.make_demo import main
        main()
    with pymupdf.open(DEMO / "presentation.pdf") as doc:
        return [p.get_pixmap(dpi=150, colorspace=pymupdf.csGRAY).tobytes("png") for p in doc]


def test_ocr_ready():
    assert ocr_ready()


def test_scanned_pdf(tmp_path):
    scan = pymupdf.open()
    for png in _pages_as_images(tmp_path)[:2]:
        page = scan.new_page()
        page.insert_image(page.rect, stream=png)
    path = tmp_path / "scan.pdf"
    scan.save(path)
    text = file_text(path)
    assert "--- стр. 1 (OCR) ---" in text and "--- стр. 2 (OCR) ---" in text
    assert "АгроСкан" in text and "Агросенсор" in text


def test_photo(tmp_path):
    path = tmp_path / "photo.png"
    path.write_bytes(_pages_as_images(tmp_path)[0])
    text = file_text(path)
    assert "(OCR)" in text and "Тамбов" in text


def test_text_pdf_is_not_ocred():
    text = file_text(DEMO / "presentation.pdf")
    assert "(OCR)" not in text and "АгроСкан" in text
