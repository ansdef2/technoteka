"""Общие функции для карточки Технотека.ИИ.

Один источник правды — schema/card_schema_v0.json. Отсюда строятся:
  * схема для структурированного вывода LLM (режимы full и flat);
  * текст инструкции к полям для промпта;
  * разбор ответа LLM и эталона в единый вид;
  * проверка цитат по исходному тексту.

Канонический вид карточки (и ответа модели, и эталона):
    {"<поле>": {"value": <значение или None>, "quote": <цитата или None>}, ...}
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SCHEMA = ROOT / "schema" / "card_schema_v0.json"

LIST_SEP = re.compile(r"\s*(?:\n|\|)\s*")  # элементы списков/таблиц: перевод строки или « | »
KIND_RU = {"extract": "извлечь", "infer": "определить", "generate": "сформулировать"}


# ---------------------------------------------------------------- схема

def load_schema(path: str | Path = DEFAULT_SCHEMA) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def fields(schema: dict) -> list[tuple[str, dict]]:
    return list(schema["properties"].items())


def _clean(node: dict) -> dict:
    """Схема значения без служебных x-ключей и без pattern/maxLength (провайдеры их часто не поддерживают)."""
    keep = {"type", "enum", "items", "properties", "required", "additionalProperties",
            "minimum", "maximum", "description", "title"}
    out = {}
    for k, v in node.items():
        if k not in keep:
            continue
        if k == "items" and isinstance(v, dict):
            v = _clean(v)
        elif k == "properties":
            v = {pk: _clean(pv) for pk, pv in v.items()}
        out[k] = v
    return out


def _nullable(node: dict) -> dict:
    node = dict(node)
    t = node.get("type")
    node["type"] = [t, "null"] if isinstance(t, str) else t
    if "enum" in node:
        node["enum"] = list(node["enum"]) + [None]
    return node


def format_hint(spec: dict) -> str:
    m = spec["x-match"]
    if "enum" in spec:
        return "одно значение из списка: " + "; ".join(spec["enum"])
    if m == "list" and "enum" in spec.get("items", {}):
        return "одно или несколько значений из списка: " + "; ".join(spec["items"]["enum"])
    if m == "list":
        return "список строк"
    if m == "table":
        return "строки «параметр: значение»"
    if m == "number":
        return f"целое число {spec.get('minimum', '')}–{spec.get('maximum', '')}"
    return "строка"


def llm_schema(schema: dict, mode: str = "full") -> dict:
    """Схема ответа для structured output.

    full — типы, enum, массивы, null для пустых значений.
    flat — все значения строки (пусто = нет данных), списки и таблицы через « | »;
           запасной режим для провайдеров со слабой поддержкой JSON Schema.
    """
    props = {}
    for key, spec in fields(schema):
        desc = f"{spec['title']}. {spec['description']}"
        if mode == "full":
            value = _nullable(_clean(spec))
            value.pop("title", None)
            value["description"] = desc
            quote = {"type": ["string", "null"], "description": "Дословная цитата из материалов"}
        elif mode == "flat":
            hint = format_hint(spec)
            if spec["x-match"] in ("list", "table"):
                hint += ", элементы через « | »"
            value = {"type": "string", "description": f"{desc} Формат: {hint}. Пустая строка — нет данных."}
            quote = {"type": "string", "description": "Дословная цитата из материалов или пустая строка"}
        else:
            raise ValueError(mode)
        props[key] = {"type": "object", "properties": {"value": value, "quote": quote},
                      "required": ["value", "quote"], "additionalProperties": False}
    return {"type": "object", "properties": props, "required": list(props), "additionalProperties": False}


def field_guide(schema: dict) -> str:
    """Описание полей для промпта (и для гайдлайна разметки)."""
    lines = []
    for key, spec in fields(schema):
        lines.append(f"- {key} — {spec['title']} [{KIND_RU[spec['x-kind']]}]: {spec['description']}. "
                     f"Формат: {format_hint(spec)}.")
    return "\n".join(lines)


# ---------------------------------------------------------------- разбор значений

def _split(s: str) -> list[str]:
    return [x.strip(" ;•-\t") for x in LIST_SEP.split(s) if x.strip(" ;•-\t")]


def _parse_table(v) -> list[dict] | None:
    if v in (None, "", []):
        return None
    rows = v if isinstance(v, list) else _split(str(v))
    out = []
    for r in rows:
        if isinstance(r, dict):
            out.append({"name": str(r.get("name", "")).strip(), "value": str(r.get("value", "")).strip()})
        else:
            name, _, val = str(r).partition(":")
            out.append({"name": name.strip(), "value": val.strip()})
    return out or None


def normalize_value(spec: dict, v):
    """Приводит значение (из LLM, full/flat, или из ячейки Excel) к каноническому типу."""
    if v is None or (isinstance(v, str) and not v.strip()):
        return None
    m = spec["x-match"]
    if m == "table":
        return _parse_table(v)
    if m == "list":
        items = v if isinstance(v, list) else _split(str(v))
        items = [str(i).strip() for i in items if str(i).strip()]
        if "enum" not in spec.get("items", {}):
            items = [i.lower() for i in items]
        return items or None
    if m == "number":
        mt = re.search(r"\d+", str(v))
        return int(mt.group()) if mt else None
    return str(v).strip()


def normalize_card(schema: dict, raw: dict) -> dict:
    card = {}
    for key, spec in fields(schema):
        item = raw.get(key) or {}
        if not isinstance(item, dict):
            item = {"value": item, "quote": None}
        q = item.get("quote")
        card[key] = {"value": normalize_value(spec, item.get("value")),
                     "quote": q.strip() if isinstance(q, str) and q.strip() else None}
    return card


def check_card(schema: dict, card: dict) -> list[str]:
    """Ошибки формата: значения вне справочника, неверные коды, превышение длины."""
    errs = []
    for key, spec in fields(schema):
        v = card.get(key, {}).get("value")
        if v is None:
            continue
        if "enum" in spec and v not in spec["enum"]:
            errs.append(f"{key}: «{v}» нет в справочнике")
        if spec.get("items", {}).get("enum"):
            bad = [i for i in v if i not in spec["items"]["enum"]]
            if bad:
                errs.append(f"{key}: нет в справочнике {bad}")
        if "pattern" in spec and isinstance(v, str) and not re.match(spec["pattern"], v):
            errs.append(f"{key}: «{v}» не соответствует формату")
        if spec["x-match"] == "number" and not (spec.get("minimum", -1e9) <= v <= spec.get("maximum", 1e9)):
            errs.append(f"{key}: {v} вне диапазона")
        if "maxLength" in spec and isinstance(v, str) and len(v) > spec["maxLength"]:
            errs.append(f"{key}: длина {len(v)} > {spec['maxLength']}")
        if "maxItems" in spec and isinstance(v, list) and len(v) > spec["maxItems"]:
            errs.append(f"{key}: элементов {len(v)} > {spec['maxItems']}")
    return errs


# ---------------------------------------------------------------- цитаты

def _norm_text(s: str) -> str:
    s = s.lower().replace("ё", "е")
    s = re.sub(r"[«»“”„\"']", '"', s)
    s = re.sub(r"[‐-―−]", "-", s)
    return re.sub(r"\s+", " ", s).strip()


def quote_score(quote: str | None, source: str) -> float | None:
    """0–100: насколько цитата дословно присутствует в исходнике. None — цитаты нет."""
    if not quote:
        return None
    q, src = _norm_text(quote), _norm_text(source)
    if q in src:
        return 100.0
    from rapidfuzz import fuzz
    return float(fuzz.partial_ratio(q, src))


QUOTE_OK = 90.0  # порог «цитата найдена»
