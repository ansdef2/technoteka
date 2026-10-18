"""ML-модуль: контракт между бэкендом и извлечением (B03).

Бэкенд вызывает ровно одну функцию — extract_card(). Всё, что внутри (парсинг, промпт,
провайдер, проверка цитат), меняется ML-разработчиками без правок бэкенда, пока соблюдён
формат ExtractionResult. Если позже понадобится отдельный сервис, эта же функция
оборачивается в POST /extract — контракт не меняется.

    from ml.extract import extract_card
    result = extract_card([Path("a.pdf"), Path("b.docx")])
    result.card["product_name"]  # {"value": ..., "quote": ..., "quote_score": 0..100 | None, "verified": bool}
"""
from __future__ import annotations

import json
import os
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

from tools.card import QUOTE_OK, check_card, llm_schema, load_schema, normalize_card, quote_score
from tools.doc_text import approx_tokens, file_text
from tools.prompt import SYSTEM, user_message

MAX_INPUT_TOKENS = int(os.environ.get("MAX_INPUT_TOKENS", "100000"))  # под контекст выбранной модели


@dataclass
class ExtractionResult:
    card: dict                      # поле → {value, quote, quote_score, verified}
    provider: str = ""
    model: str = ""
    schema_mode: str = ""           # full | flat — какой режим structured output сработал
    schema_version: str = ""
    latency_s: float = 0.0
    tokens_in: int = 0
    tokens_out: int = 0
    warnings: list[str] = field(default_factory=list)   # показываем пользователю/логируем
    errors: list[str] = field(default_factory=list)     # непустой → карточка не заполнена

    @property
    def ok(self) -> bool:
        return not self.errors

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False)


def _provider():
    from b02.providers import PROVIDERS
    from ml.heuristic import DemoProvider
    return {**PROVIDERS, "demo": DemoProvider}[os.environ.get("LLM_PROVIDER", "mock")]()


def extract_card(files: list[Path], schema: dict | None = None, provider=None) -> ExtractionResult:
    schema = schema or load_schema()
    provider = provider or _provider()
    res = ExtractionResult(card={}, provider=provider.name, model=getattr(provider, "model", ""),
                           schema_version=schema.get("x-version", ""))

    parts = []
    for f in files:
        try:
            t = file_text(f).strip()
        except Exception as e:
            res.warnings.append(f"{f.name}: не удалось прочитать ({type(e).__name__})")
            continue
        if len(t) < 200:
            res.warnings.append(f"{f.name}: почти нет текста — возможно, скан")
        if t:
            parts.append(f"=== Файл: {f.name} ===\n{t}")
    text = "\n\n".join(parts)
    if not text:
        res.errors.append("в загруженных файлах нет текста")
        return res
    if approx_tokens(text) > MAX_INPUT_TOKENS:  # v1: обрезаем; RAG — итерация 2 (D08)
        text = text[: int(MAX_INPUT_TOKENS * 3.5)]
        res.warnings.append("материалы длиннее контекста модели — учтена только начальная часть")

    t0 = time.time()
    raw, usage = None, {}
    for mode in ("full", "flat"):
        try:
            raw_text, usage, _ = provider.complete(SYSTEM, user_message(schema, text), llm_schema(schema, mode))
            raw = json.loads(raw_text)
            res.schema_mode = mode
            break
        except Exception as e:
            res.warnings.append(f"режим {mode}: {type(e).__name__}: {str(e)[:200]}")
    res.latency_s = round(time.time() - t0, 2)
    res.tokens_in = int(usage.get("prompt_tokens") or usage.get("input_tokens") or 0)
    res.tokens_out = int(usage.get("completion_tokens") or usage.get("output_tokens") or 0)
    if raw is None:
        res.errors.append("модель не вернула ответ по схеме")
        return res

    card = normalize_card(schema, raw)
    for problem in check_card(schema, card):  # значение вне справочника/формата → поле очищаем
        key = problem.split(":", 1)[0]
        res.warnings.append(f"значение отброшено — {problem}")
        card[key] = {"value": None, "quote": None}
    for key, v in card.items():
        sc = quote_score(v["quote"], text) if v["value"] is not None else None
        v["quote_score"] = None if sc is None else round(sc)
        v["verified"] = sc is not None and sc >= QUOTE_OK
    res.card = card
    return res
