"""Логотип Технотеки: знак «Т.» и горизонтальные версии — буквы Unbounded, переведённые в кривые.

python3 docs/make_logo.py frontend/node_modules/@fontsource/unbounded/files frontend/public/brand
"""
import sys
from pathlib import Path

from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont

FILES, OUT = Path(sys.argv[1]), Path(sys.argv[2])
OUT.mkdir(parents=True, exist_ok=True)

BRAND, INK, AMBER, WHITE, SKY = "#1f4e79", "#1d2733", "#f4b223", "#ffffff", "#9dbbe0"


def font(weight):
    return TTFont(FILES / f"unbounded-cyrillic-{weight}-normal.woff2")


def glyph_path(f, ch, x, y, size):
    """Контур буквы ch: левый край x, базовая линия y, кегль size (px). → (d, ширина)."""
    gs, cmap, upm = f.getGlyphSet(), f.getBestCmap(), f["head"].unitsPerEm
    name = cmap[ord(ch)]
    s = size / upm
    pen = SVGPathPen(gs)
    gs[name].draw(TransformPen(pen, (s, 0, 0, -s, x, y)))
    return pen.getCommands(), f["hmtx"][name][0] * s


def text_paths(f, text, x, y, size, tracking=0.0):
    ds, cx = [], x
    for ch in text:
        d, adv = glyph_path(f, ch, cx, y, size)
        ds.append(d)
        cx += adv + tracking * size
    return " ".join(ds), cx - tracking * size


def bounds(f, ch, size):
    gs, cmap, upm = f.getGlyphSet(), f.getBestCmap(), f["head"].unitsPerEm
    bp = BoundsPen(gs)
    gs[cmap[ord(ch)]].draw(bp)
    return [v * size / upm for v in bp.bounds]  # xMin, yMin, xMax, yMax (вверх от базовой линии)


# ---- знак «Т.»: квадрат 32×32 (скругление 7 — как у прежнего значка), буква Т Unbounded 700, янтарная точка
def mark(ground=BRAND, letter=WHITE, dot=AMBER):
    f = font(700)
    size = 23.5
    x0, _, x1, top = bounds(f, "Т", size)
    w = x1 - x0
    base = 16 + top / 2 + 1.2          # оптически по центру, чуть ниже — под точку
    x = 16 - w / 2 - x0 - 1.6           # чуть левее — справа встаёт точка
    d, _ = glyph_path(f, "Т", x, base, size)
    r = 2.7
    cx, cy = x + x0 + w + r + 1.0, base - r
    return (f'<rect width="32" height="32" rx="7" fill="{ground}"/>'
            f'<path d="{d}" fill="{letter}"/><circle cx="{cx:.2f}" cy="{cy:.2f}" r="{r}" fill="{dot}"/>')


def svg(w, h, body, title):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w:.1f} {h:.1f}" width="{w:.0f}" height="{h:.0f}" '
            f'role="img" aria-label="{title}"><title>{title}</title>{body}</svg>\n')


(OUT / "mark.svg").write_text(svg(32, 32, mark(), "Технотека.ИИ"), encoding="utf-8")
(OUT / "mark-inverse.svg").write_text(svg(32, 32, mark(WHITE, BRAND, AMBER), "Технотека.ИИ"), encoding="utf-8")


# ---- горизонтальная версия: знак 48 + «Технотека» + точка + «ИИ»
def horizontal(word, ii, dot, ground_mark):
    f = font(600)
    H, size, gap = 48, 25, 14
    base = 24 + bounds(f, "Т", size)[3] / 2
    x = 48 + gap
    d1, x = text_paths(f, "Технотека", x, base, size, 0.01)
    r = size * 0.11
    cx = x + r + size * 0.06
    d2, xe = text_paths(f, "ИИ", cx + r + size * 0.06, base, size, 0.01)
    body = (f'<g transform="scale(1.5)">{ground_mark}</g>'
            f'<path d="{d1}" fill="{word}"/><circle cx="{cx:.2f}" cy="{base - r:.2f}" r="{r:.2f}" fill="{dot}"/>'
            f'<path d="{d2}" fill="{ii}"/>')
    return svg(xe + 2, H, body, "Технотека.ИИ")


(OUT / "logo-horizontal.svg").write_text(horizontal(INK, BRAND, AMBER, mark()), encoding="utf-8")
(OUT / "logo-horizontal-inverse.svg").write_text(horizontal(WHITE, SKY, AMBER, mark(WHITE, BRAND, AMBER)), encoding="utf-8")
print("ok:", ", ".join(sorted(p.name for p in OUT.glob("*.svg"))))


# ---- контраст (WCAG 2): пары, которые бренд использует
def lum(h):
    h = h.lstrip("#")
    c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    c = [v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4 for v in c]
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]


def ratio(a, b):
    la, lb = sorted((lum(a), lum(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


pairs = [("ink", INK, "bg", "#f4f6f9"), ("ink", INK, "surface", WHITE), ("muted", "#5f6b7b", "bg", "#f4f6f9"),
         ("muted", "#5f6b7b", "surface", WHITE), ("muted", "#5f6b7b", "ai-tint", "#e8f1fb"), ("white", WHITE, "brand", BRAND), ("brand", BRAND, "surface", WHITE),
         ("brand", BRAND, "ai-tint", "#e8f1fb"), ("quote-ink", "#44546a", "surface", WHITE),
         ("warn-ink", "#9a5c00", "warn-tint", "#fff7e6"), ("danger", "#cf1322", "danger-tint", "#fff1f0"),
         ("danger", "#cf1322", "surface", WHITE), ("amber", AMBER, "brand", BRAND), ("amber", AMBER, "surface", WHITE),
         ("sky", SKY, "brand", BRAND), ("ink", INK, "amber", AMBER)]
for a, ca, b, cb in pairs:
    print(f"  {a:>9} на {b:<11} {ratio(ca, cb):5.2f}:1")
