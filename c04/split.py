"""C04 — разбиение комплектов на dev / test.

1) Заготовка манифеста по папке с материалами (колонку source заполнить вручную):
    python -m c04.split scan data/raw --out data/manifest.csv
2) Разбиение (стратификация по source, фиксированный seed; комплекты B02 — принудительно в dev):
    python -m c04.split split data/manifest.csv --dev 10 --force-dev TT-001,TT-002,TT-003,TT-004,TT-005 --out data/split.csv
3) Добавление новых комплектов (C07): старые назначения не меняются, новые идут в test:
    python -m c04.split split data/manifest.csv --dev 10 --existing data/split.csv --out data/split.csv

source: egisu | fips | mtk_site | respondent | vitrina
"""
from __future__ import annotations

import argparse
import csv
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.doc_text import approx_tokens, set_files, set_text  # noqa: E402

SEED = 20261007
FIELDS = ["set_id", "source", "n_files", "formats", "approx_tokens", "note"]


def scan(raw: Path, out: Path):
    rows = []
    for d in sorted(p for p in raw.iterdir() if p.is_dir() and not p.name.startswith(".")):
        files = set_files(d)
        text, warns = set_text(d)
        rows.append({"set_id": d.name, "source": "", "n_files": len(files),
                     "formats": ",".join(sorted({f.suffix.lower().lstrip(".") for f in files})),
                     "approx_tokens": approx_tokens(text), "note": "; ".join(warns)})
    _write(out, rows, FIELDS)
    print(f"{out}: {len(rows)} комплектов. Заполните колонку source.")


def _read(path: Path) -> list[dict]:
    with path.open(encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def _write(path: Path, rows: list[dict], cols: list[str]):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def split(manifest: Path, n_dev: int, out: Path, existing: Path | None, force_dev: list[str] = ()):
    rows = _read(manifest)
    missing = [r["set_id"] for r in rows if not r.get("source")]
    if missing:
        sys.exit(f"Не заполнен source у: {', '.join(missing)}")
    ids = {r["set_id"] for r in rows}
    unknown = [s for s in force_dev if s not in ids]
    if unknown:
        sys.exit(f"Нет в манифесте: {', '.join(unknown)}")
    if len(force_dev) > n_dev:
        sys.exit(f"--force-dev ({len(force_dev)}) больше, чем --dev ({n_dev})")
    fixed = {r["set_id"]: r["split"] for r in _read(existing)} if existing and existing.exists() else {}
    if not fixed:  # комплекты, на которых уже смотрели ответы модели (B02), — только в dev
        fixed = {s: "dev" for s in force_dev}
        n_dev -= len(force_dev)
        frozen = False
    else:
        frozen = True
    new = [r for r in rows if r["set_id"] not in fixed]

    if frozen:  # dev заморожен; всё новое — в test
        assign = {r["set_id"]: "test" for r in new}
    elif not new or n_dev == 0:
        assign = {r["set_id"]: "test" for r in new}
    else:
        # dev делится между источниками пропорционально их доле (метод наибольших остатков),
        # внутри источника — случайный выбор с фиксированным seed (воспроизводимо)
        rng = random.Random(SEED)
        strata = defaultdict(list)
        for r in new:
            strata[r["source"]].append(r)
        total = len(new)
        quota = {s: n_dev * len(v) / total for s, v in strata.items()}
        alloc = {s: int(q) for s, q in quota.items()}
        for s in sorted(quota, key=lambda s: quota[s] - alloc[s], reverse=True)[: n_dev - sum(alloc.values())]:
            alloc[s] += 1
        assign = {}
        for s, items in strata.items():
            items = sorted(items, key=lambda r: r["set_id"])
            rng.shuffle(items)
            for i, r in enumerate(items):
                assign[r["set_id"]] = "dev" if i < alloc[s] else "test"
    result = []
    for r in rows:
        result.append({**r, "split": fixed.get(r["set_id"]) or assign[r["set_id"]]})
    _write(out, result, FIELDS + ["split"])

    c = Counter((r["source"], r["split"]) for r in result)
    print(f"{out}: dev {sum(r['split'] == 'dev' for r in result)}, test {sum(r['split'] == 'test' for r in result)}")
    for s in sorted({r["source"] for r in result}):
        print(f"  {s:12} dev {c[(s, 'dev')]:>2}  test {c[(s, 'test')]:>2}")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("scan")
    s.add_argument("raw")
    s.add_argument("--out", required=True)
    p = sub.add_parser("split")
    p.add_argument("manifest")
    p.add_argument("--dev", type=int, default=10)
    p.add_argument("--out", required=True)
    p.add_argument("--existing")
    p.add_argument("--force-dev", default="", help="комплекты через запятую, которые обязательно в dev (B02)")
    a = ap.parse_args()
    if a.cmd == "scan":
        scan(Path(a.raw), Path(a.out))
    else:
        force = [s.strip() for s in a.force_dev.split(",") if s.strip()]
        split(Path(a.manifest), a.dev, Path(a.out), Path(a.existing) if a.existing else None, force)


if __name__ == "__main__":
    main()
