"""Адаптеры LLM-провайдеров для B02. Каждый возвращает (текст ответа, usage, сырой ответ).

Ключи берутся из переменных окружения (см. README):
  Yandex AI Studio: YANDEX_API_KEY, YANDEX_FOLDER_ID, [YANDEX_MODEL], [YANDEX_BASE_URL]
  GigaChat:        GIGACHAT_AUTH_KEY, [GIGACHAT_SCOPE], [GIGACHAT_MODEL], [GIGACHAT_CA_BUNDLE]
"""
from __future__ import annotations

import json
import os
import time
import uuid

import requests

TIMEOUT = 180


class Provider:
    name = "base"
    model = ""

    def complete(self, system: str, user: str, schema: dict) -> tuple[str, dict, dict]:
        raise NotImplementedError


class YandexProvider(Provider):
    """Yandex AI Studio, OpenAI-совместимый Chat Completions + response_format=json_schema.

    Логирование запросов на стороне Яндекса по умолчанию включено — отключаем заголовком
    x-data-logging-enabled: false (документация AI Studio, «Отключение логирования»).
    """
    name = "yandex"

    def __init__(self):
        self.key = os.environ["YANDEX_API_KEY"]
        self.folder = os.environ["YANDEX_FOLDER_ID"]
        # URI модели сверить в консоли AI Studio: например yandexgpt/latest, yandexgpt/rc или Alice AI LLM
        self.model = os.environ.get("YANDEX_MODEL", "yandexgpt/latest")
        self.base = os.environ.get("YANDEX_BASE_URL", "https://ai.api.cloud.yandex.net/v1").rstrip("/")

    def complete(self, system, user, schema):
        body = {
            "model": f"gpt://{self.folder}/{self.model}",
            "temperature": 0,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "response_format": {"type": "json_schema",
                                "json_schema": {"name": "card", "schema": schema, "strict": True}},
        }
        r = requests.post(f"{self.base}/chat/completions", json=body, timeout=TIMEOUT, headers={
            "Authorization": f"Api-Key {self.key}",
            "x-data-logging-enabled": "false",
        })
        r.raise_for_status()
        data = r.json()
        text = data["choices"][0]["message"]["content"]
        return text, data.get("usage", {}), data


class GigaChatProvider(Provider):
    """GigaChat API v2: POST /v2/chat/completions, model_options.response_format (json_schema, strict).

    Токен доступа получается по ключу авторизации и живёт 30 минут.
    Сервер OAuth использует сертификат НУЦ Минцифры: укажите путь к Russian Trusted Root CA
    в GIGACHAT_CA_BUNDLE (проверку TLS не отключаем).
    """
    name = "gigachat"
    OAUTH = "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"

    def __init__(self):
        self.auth_key = os.environ["GIGACHAT_AUTH_KEY"]
        self.scope = os.environ.get("GIGACHAT_SCOPE", "GIGACHAT_API_CORP")  # PERS — физлица, B2B/CORP — юрлица
        self.model = os.environ.get("GIGACHAT_MODEL", "GigaChat-2-Max")
        self.base = os.environ.get("GIGACHAT_BASE_URL", "https://api.giga.chat").rstrip("/")
        self.verify = os.environ.get("GIGACHAT_CA_BUNDLE") or True
        self._token, self._exp = None, 0.0

    def _auth(self):
        if self._token and time.time() < self._exp - 60:
            return self._token
        r = requests.post(self.OAUTH, data={"scope": self.scope}, verify=self.verify, timeout=30, headers={
            "Authorization": f"Basic {self.auth_key}", "RqUID": str(uuid.uuid4()),
            "Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json"})
        r.raise_for_status()
        d = r.json()
        self._token = d["access_token"]
        exp = d.get("expires_at", 0)
        self._exp = exp / 1000 if exp > 1e11 else (exp or time.time() + 1500)
        return self._token

    def complete(self, system, user, schema):
        body = {
            "model": self.model,
            "messages": [{"role": "system", "content": [{"text": system}]},
                         {"role": "user", "content": [{"text": user}]}],
            "model_options": {"temperature": 0,
                              "response_format": {"type": "json_schema", "schema": schema, "strict": True}},
        }
        r = requests.post(f"{self.base}/v2/chat/completions", json=body, verify=self.verify, timeout=TIMEOUT,
                          headers={"Authorization": f"Bearer {self._auth()}"})
        r.raise_for_status()
        data = r.json()
        return _find_text(data), _find_usage(data), data


class MockProvider(Provider):
    """Без сети: проверка пайплайна. Берёт первую строку текста как наименование, остальное пусто."""
    name = "mock"
    model = "mock"

    def complete(self, system, user, schema):
        body = user.split("<<<", 1)[-1]
        first = next((ln.strip() for ln in body.splitlines() if ln.strip() and not ln.startswith("===")), "")
        out = {k: {"value": None, "quote": None} for k in schema["properties"]}
        out["product_name"] = {"value": first[:120], "quote": first[:120]}
        out["org_name"] = {"value": "ООО «Выдумка»", "quote": "ООО «Выдумка»"}  # заведомая «галлюцинация»
        return json.dumps(out, ensure_ascii=False), {"prompt_tokens": len(user) // 4, "completion_tokens": 200}, {}


def _find_text(data):
    """Ответ v2 может быть вложен по-разному — берём первый текст ассистента, похожий на JSON."""
    stack = [data]
    while stack:
        x = stack.pop(0)
        if isinstance(x, dict):
            t = x.get("text") or x.get("content")
            if isinstance(t, str) and t.lstrip().startswith("{"):
                return t
            stack.extend(x.values())
        elif isinstance(x, list):
            stack.extend(x)
    raise ValueError("в ответе не найден JSON-текст: " + json.dumps(data, ensure_ascii=False)[:500])


def _find_usage(data):
    if isinstance(data, dict):
        if "usage" in data and isinstance(data["usage"], dict):
            return data["usage"]
        for v in data.values():
            u = _find_usage(v)
            if u:
                return u
    return {}


PROVIDERS = {"yandex": YandexProvider, "gigachat": GigaChatProvider, "mock": MockProvider}
