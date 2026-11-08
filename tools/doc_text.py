"""Материалы разработки → один текст для модели.

Комплект = папка с файлами одной разработки (или один файл).
Поддержка: PDF (pymupdf), DOCX (python-docx), PPTX (python-pptx), HTML (beautifulsoup4), TXT/MD,
JPG/PNG (фото и сканы документов).
В текст вставляются метки «--- стр. N ---» / «--- слайд N ---», чтобы разметчик и модель
могли сослаться на место цитаты. Страницы без текстового слоя (сканы, фото) распознаются OCR —
Tesseract внутри pymupdf; метка такой страницы — «--- стр. N (OCR) ---».
"""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

IMAGES = {".jpg", ".jpeg", ".png"}
SUPPORTED = {".pdf", ".docx", ".pptx", ".txt", ".md", ".html", ".htm"} | IMAGES

# служебные блоки страницы, которые не относятся к описанию продукта
HTML_DROP = ["script", "style", "noscript", "svg", "nav", "header", "footer", "form", "iframe", "button"]

# OCR: языковые данные — пакеты tesseract-ocr-rus/-eng (путь — TESSDATA_PREFIX, см. Dockerfile)
OCR_LANG = os.environ.get("OCR_LANG", "rus+eng")
OCR_MAX_PAGES = int(os.environ.get("OCR_MAX_PAGES", "30"))  # на файл: OCR — около секунды на страницу
OCR_MIN_CHARS = 30  # меньше текста на странице с картинкой — считаем её сканом


@lru_cache(maxsize=1)
def ocr_ready() -> bool:
    """Есть ли языковые данные Tesseract для OCR_LANG (показывается в /api/health)."""
    try:
        import pymupdf
        tessdata = Path(pymupdf.get_tessdata())
    except Exception:
        return False
    return all((tessdata / f"{lang}.traineddata").exists() for lang in OCR_LANG.split("+"))


def _pdf(path: Path) -> str:
    """PDF или картинка; страницы-сканы распознаются OCR (не больше OCR_MAX_PAGES на файл)."""
    import pymupdf
    out, ocr_left = [], OCR_MAX_PAGES
    with pymupdf.open(path) as src:
        doc = src if src.is_pdf else pymupdf.open("pdf", src.convert_to_pdf())
        for i, page in enumerate(doc, 1):
            text, mark = page.get_text(), ""
            if len(text.strip()) < OCR_MIN_CHARS and page.get_images():
                if ocr_left <= 0:
                    mark = " (скан, не распознан: лимит OCR)"
                else:
                    ocr_left -= 1
                    try:
                        text = page.get_text(textpage=page.get_textpage_ocr(language=OCR_LANG, dpi=300, full=True))
                        mark = " (OCR)"
                    except Exception:  # нет языковых данных Tesseract (локальный запуск без него)
                        mark = " (скан, OCR недоступен)"
            out.append(f"--- стр. {i}{mark} ---\n{text}")
    return "\n".join(out)


def _docx(path: Path) -> str:
    from docx import Document
    d = Document(str(path))
    parts = [p.text for p in d.paragraphs if p.text.strip()]
    for t in d.tables:
        for row in t.rows:
            cells = []
            for c in row.cells:  # объединённые ячейки python-docx повторяет — убираем дубли подряд
                if not cells or cells[-1] != c.text.strip():
                    cells.append(c.text.strip())
            parts.append(" | ".join(cells))
    return "\n".join(parts)


def _pptx(path: Path) -> str:
    from pptx import Presentation
    out = []
    for i, slide in enumerate(Presentation(str(path)).slides, 1):
        out.append(f"--- слайд {i} ---")
        for shape in slide.shapes:
            if shape.has_text_frame and shape.text_frame.text.strip():
                out.append(shape.text_frame.text)
            elif getattr(shape, "has_table", False) and shape.has_table:
                for row in shape.table.rows:
                    out.append(" | ".join(c.text.strip() for c in row.cells))
        if slide.has_notes_slide and slide.notes_slide.notes_text_frame.text.strip():
            out.append("Заметки: " + slide.notes_slide.notes_text_frame.text)
    return "\n".join(out)


def _html(path: Path) -> str:
    """Сохранённая веб-страница → текст. Таблицы — строками «ячейка | ячейка»."""
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(path.read_bytes(), "html.parser")
    for tag in soup(HTML_DROP):
        tag.decompose()
    for row in soup.find_all("tr"):
        cells = [c.get_text(" ", strip=True) for c in row.find_all(["td", "th"])]
        row.replace_with(soup.new_string("\n" + " | ".join(c for c in cells if c) + "\n"))
    title = soup.title.get_text(strip=True) if soup.title else ""
    body = soup.body or soup
    lines = [ln.strip() for ln in body.get_text("\n").splitlines()]
    out, prev = [], None
    for ln in lines:  # убираем пустые строки и повторы подряд (меню, дубли блоков)
        if ln and ln != prev:
            out.append(ln)
        prev = ln
    return (f"Заголовок страницы: {title}\n" if title else "") + "\n".join(out)


def file_text(path: Path) -> str:
    ext = path.suffix.lower()
    if ext == ".pdf" or ext in IMAGES:
        return _pdf(path)
    if ext == ".docx":
        return _docx(path)
    if ext == ".pptx":
        return _pptx(path)
    if ext in (".html", ".htm"):
        return _html(path)
    return path.read_text(encoding="utf-8", errors="replace")


def set_files(set_path: Path) -> list[Path]:
    if set_path.is_file():
        return [set_path] if set_path.suffix.lower() in SUPPORTED else []
    return sorted(p for p in set_path.rglob("*") if p.is_file() and p.suffix.lower() in SUPPORTED
                  and not p.name.startswith(("~$", ".")))


def set_text(set_path: Path) -> tuple[str, list[str]]:
    """Текст комплекта с разделителями по файлам и список предупреждений."""
    parts, warnings = [], []
    for f in set_files(set_path):
        try:
            t = file_text(f).strip()
        except Exception as e:  # битый файл не должен ронять весь прогон
            warnings.append(f"{f.name}: не удалось прочитать ({type(e).__name__}: {e})")
            continue
        body = "\n".join(ln for ln in t.splitlines() if not ln.startswith("--- "))
        if len(body.strip()) < 200:
            warnings.append(f"{f.name}: почти нет текста ({len(body.strip())} симв.) — возможно, скан")
        parts.append(f"=== Файл: {f.name} ===\n{t}")
    if not parts:
        warnings.append("в комплекте нет читаемых файлов")
    return "\n\n".join(parts), warnings


def approx_tokens(text: str) -> int:
    """Грубая оценка для русского текста (~3,5 символа на токен)."""
    return int(len(text) / 3.5)
