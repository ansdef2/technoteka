"""SQLite: одно соединение на операцию (бэкенд однопроцессный, извлечение — в фоновых потоках)."""
from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA_DIR = Path(os.environ.get("DATA_DIR", HERE.parent / "var")).resolve()
DB_PATH = DATA_DIR / "tehnoteka.db"
FILES_DIR = DATA_DIR / "files"


def init() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    FILES_DIR.mkdir(parents=True, exist_ok=True)
    with connect() as c:
        c.executescript((HERE / "schema.sql").read_text(encoding="utf-8"))


@contextmanager
def connect():
    c = sqlite3.connect(DB_PATH, timeout=15)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys = ON")
    try:
        yield c
        c.commit()
    finally:
        c.close()


def row(c, sql, *args):
    r = c.execute(sql, args).fetchone()
    return dict(r) if r else None


def rows(c, sql, *args):
    return [dict(r) for r in c.execute(sql, args).fetchall()]


def jload(s, default=None):
    return json.loads(s) if s else default


def jdump(x) -> str:
    return json.dumps(x, ensure_ascii=False)
