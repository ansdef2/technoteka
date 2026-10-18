"""C02 — загрузка открытых материалов комплектов по списку c02/sources.csv.

    python -m c02.download --out data/raw                  # всё, уже скачанное пропускается
    python -m c02.download --out data/raw --only TT-007,TT-010
    python -m c02.download --out data/raw --manifest data/manifest.csv   # + манифест для c04.split

Каждый файл кладётся в data/raw/<set_id>/<file>; рядом — .<file>.meta.json (URL, дата, тип),
его парсер не читает. Если основной URL не отдал файл, пробуется alt_url
(для патентов: Google Patents ↔ ФИПС). HTML сохраняется как есть; страницы, которые
собираются скриптами в браузере, дадут мало текста — их видно в отчёте (колонка chars).
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import requests  # noqa: E402

from tools.doc_text import approx_tokens, set_files, set_text  # noqa: E402

SOURCES = Path(__file__).resolve().parent / "sources.csv"
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
EXT = {"application/pdf": ".pdf", "text/html": ".html",
       "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
       "application/vnd.openxmlformats-officedocument.presentationml.presentation": ".pptx"}


def read_sources(path: Path) -> list[dict]:
    with path.open(encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def _ext(resp: requests.Response, url: str) -> str:
    ctype = resp.headers.get("Content-Type", "").split(";")[0].strip().lower()
    if ctype in EXT:
        return EXT[ctype]
    if resp.content[:5] == b"%PDF-":
        return ".pdf"
    if resp.content[:2] == b"PK":  # zip-контейнер: docx/pptx — по имени из URL
        return ".pptx" if "ppt" in url.lower() else ".docx"
    return ".html"


def fetch(url: str, verify) -> tuple[bytes, str] | None:
    try:
        r = requests.get(url, timeout=60, headers={"User-Agent": UA, "Accept-Language": "ru"}, verify=verify)
        r.raise_for_status()
    except requests.RequestException as e:
        print(f"      ✗ {url}: {type(e).__name__}: {str(e)[:120]}")
        return None
    if len(r.content) < 500:
        print(f"      ✗ {url}: слишком маленький ответ ({len(r.content)} байт)")
        return None
    return r.content, _ext(r, url)


def download(rows: list[dict], out: Path, verify, pause: float) -> list[dict]:
    report = []
    for row in rows:
        d = out / row["set_id"]
        d.mkdir(parents=True, exist_ok=True)
        stem = Path(row["file"]).stem
        existing = [p for p in d.glob(stem + ".*") if not p.name.startswith(".")]
        if existing:
            report.append({**row, "status": "уже есть", "saved": existing[0].name})
            continue
        print(f"  {row['set_id']} {row['file']}")
        got, used = None, None
        for url in filter(None, [row["url"], row.get("alt_url")]):
            got = fetch(url, verify)
            if got:
                used = url
                break
            time.sleep(pause)
        if not got:
            report.append({**row, "status": "НЕ СКАЧАНО", "saved": ""})
            continue
        content, ext = got
        target = d / (stem + ext)
        target.write_bytes(content)
        (d / f".{target.name}.meta.json").write_text(json.dumps(
            {"url": used, "downloaded": dt.datetime.now().isoformat(timespec="seconds"), "bytes": len(content)},
            ensure_ascii=False, indent=2), encoding="utf-8")
        report.append({**row, "status": "ок", "saved": target.name})
        time.sleep(pause)
    return report


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="data/raw")
    ap.add_argument("--sources", default=str(SOURCES))
    ap.add_argument("--only", default="", help="set_id через запятую")
    ap.add_argument("--manifest", help="записать манифест комплектов для c04.split")
    ap.add_argument("--ca-bundle", help="путь к сертификатам (для сайтов с сертификатом НУЦ Минцифры)")
    ap.add_argument("--pause", type=float, default=1.0, help="пауза между запросами, с")
    a = ap.parse_args()

    rows = read_sources(Path(a.sources))
    if a.only:
        keep = {s.strip() for s in a.only.split(",")}
        rows = [r for r in rows if r["set_id"] in keep]
    out = Path(a.out)
    report = download(rows, out, a.ca_bundle or True, a.pause)

    # отчёт по комплектам: сколько текста реально извлеклось
    print("\nКомплект  файлов  ~токенов  статус")
    sets = sorted({r["set_id"] for r in report})
    manifest = []
    for sid in sets:
        rr = [r for r in report if r["set_id"] == sid]
        d = out / sid
        text, warns = set_text(d) if d.exists() else ("", ["папки нет"])
        bad = [r["file"] for r in rr if r["status"] == "НЕ СКАЧАНО"]
        status = "ок" if not bad and not warns else "; ".join(([f"не скачано: {', '.join(bad)}"] if bad else []) + warns)
        print(f"{sid}   {len(set_files(d)) if d.exists() else 0:>4}  {approx_tokens(text):>8}  {status}")
        files = set_files(d) if d.exists() else []
        manifest.append({"set_id": sid, "source": rr[0]["source"], "n_files": len(files),
                         "formats": ",".join(sorted({f.suffix.lower().lstrip('.') for f in files})),
                         "approx_tokens": approx_tokens(text), "note": status if status != "ок" else ""})
    if a.manifest:
        from c04.split import FIELDS, _write
        _write(Path(a.manifest), manifest, FIELDS)
        print(f"\nМанифест: {a.manifest}")
    failed = sum(r["status"] == "НЕ СКАЧАНО" for r in report)
    if failed:
        print(f"\nНе скачано файлов: {failed}. Откройте ссылку в браузере и сохраните файл в папку комплекта вручную "
              f"(страница — «Сохранить как… → веб-страница, только HTML», или печать в PDF).")


if __name__ == "__main__":
    main()
