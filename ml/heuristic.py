"""Демо-провайдер без LLM: правила и регулярные выражения.

Нужен, чтобы показывать прототип и гонять фронт, пока нет ключей API (LLM_PROVIDER=demo).
Это НЕ модель: заполняет только то, что надёжно ловится шаблонами (ИНН, сайт, юрлицо,
регион, отрасль по ключевым словам, ТТХ «параметр: значение»), остальное оставляет пустым.
Каждое значение сопровождается цитатой — настоящим фрагментом текста, поэтому проверка
цитат на фронте работает так же, как с моделью.
"""
from __future__ import annotations

import json
import re

from b02.providers import Provider
from tools.card import load_schema

_SCHEMA = load_schema()
_P = _SCHEMA["properties"]

CITY_REGION = {
    "москв": "Москва", "зеленоград": "Москва", "сколково": "Москва",
    "санкт-петербург": "Санкт-Петербург", "петербург": "Санкт-Петербург",
    "екатеринбург": "Свердловская область", "новосибирск": "Новосибирская область",
    "казан": "Республика Татарстан", "иннополис": "Республика Татарстан",
    "перм": "Пермский край", "томск": "Томская область", "ижевск": "Удмуртская Республика",
    "волгоград": "Волгоградская область", "тамбов": "Тамбовская область",
    "нижний новгород": "Нижегородская область", "самар": "Самарская область",
    "уф": "Республика Башкортостан", "челябинск": "Челябинская область",
    "красноярск": "Красноярский край", "ростов-на-дону": "Ростовская область",
    "краснодар": "Краснодарский край", "воронеж": "Воронежская область",
    "белгород": "Белгородская область", "калуг": "Калужская область", "обнинск": "Калужская область",
    "дубн": "Московская область", "королёв": "Московская область", "химки": "Московская область",
}

INDUSTRY_KW = {
    "Беспилотные авиационные системы": ["бпла", "беспилот", "бвс", "дрон", "агродрон", "квадрокоптер"],
    "Медицина": ["медицин", "пациент", "протез", "клиник", "диагност", "реабилит", "маммограф"],
    "Искусственный интеллект": ["нейросет", "искусственн", "машинн обучен", "компьютерн зрени", "ии-"],
    "Робототехника": ["робот", "манипулятор", "экзоскелет"],
    "Сельское хозяйство": ["сельск", "урожа", "посев", "полив", "растениевод", "агроном", "хозяйств"],
    "Энергетика": ["энерги", "генератор", "электростанц", "топливн элемент"],
    "Связь и телекоммуникации": ["dwdm", "телеком", "оптическ сет", "связи"],
    "Микроэлектроника и приборостроение": ["прибор", "датчик", "контроллер", "измерител", "каротаж"],
    "Новые материалы и химия": ["композит", "материал", "полимер", "химическ"],
    "Машиностроение": ["машин", "станок", "привод", "электрическ машин"],
    "Строительство": ["строител", "арматур", "бетон"],
    "Космическая отрасль": ["спутник", "космическ", "дзз"],
    "Образование": ["образоват", "обучени", "школ", "учебн"],
    "IT": ["программн", "платформ", "сервис", "распознаван"],
    "Биотехнологии": ["пцр", "биотехнолог", "генетическ", "днк"],
    "Экология": ["эколог", "выброс", "очистк воздух", "бризер"],
}

STATUS_KW = [  # порядок важен: от зрелого к раннему
    ("Серийное производство", ["серийн", "производим", "выпускаем"]),
    ("Готовый продукт", ["купить", "в наличии", "цена", "заказать", "поставляем"]),
    ("Пилот", ["пилотн", "опытная эксплуатац"]),
    ("Прототип", ["прототип", "опытный образец"]),
    ("Исследование", ["исследован", "способ ", "полезная модель", "изобретени"]),
]

COOP_KW = {
    "Продажа / поставка": ["купить", "заказать", "цена", "поставк", "в наличии", "оставить заявку"],
    "Лицензирование": ["лиценз"],
    "Совместная разработка": ["совместн разработ", "кастомиз", "под задачи заказчика"],
    "Пилотное внедрение": ["пилотн проект", "пилотное внедрение", "тестовый период", "бесплатный тест"],
    "Поиск инвестора": ["инвестор", "инвестиц"],
}

ORG_RE = re.compile(r"\b(ООО|АО|ПАО|ЗАО|НАО|ФГБУ|ФГБОУ ВО|ФГАОУ ВО|ФГБУН|ИП|ГК|НПФ|НПО)\s*[«\"]([^»\"]{2,80})[»\"]")
INN_RE = re.compile(r"ИНН\s*[:№]?\s*(\d{10}|\d{12})\b")
SITE_RE = re.compile(r"\b(https?://[a-zа-я0-9.\-]+\.[a-zа-я]{2,}|www\.[a-z0-9.\-]+\.[a-z]{2,})", re.I)
TRL_RE = re.compile(r"\b(?:TRL|УГТ|УГТ-|уровень готовности[^\d]{0,20})\s*[-–:]?\s*([1-9])\b", re.I)
OKPD_RE = re.compile(r"ОКПД\s*2?\s*[:\-]?\s*(\d{2}(?:\.\d{1,2}){0,2}(?:\.\d{1,3})?)")
SKIP_PARAM = re.compile(r"сайт|телефон|e-?mail|почта|адрес|инн|огрн", re.I)
EFFECT_PARAM = re.compile(r"(экономия|прирост|снижение|рост|сокращение|увеличение|повышение)\b", re.I)
PARAM_RE = re.compile(r"^\s*([А-ЯЁA-Z][^:|\n]{2,60}?)\s*[:|]\s*([^|\n]{1,80}\d[^|\n]{0,40})\s*$")


def _stem_hit(text_l: str, kw: str) -> int:
    """Ключ из нескольких основ — все основы рядом (в пределах 30 символов)."""
    parts = kw.split()
    if len(parts) == 1:
        return text_l.count(kw)
    pat = r"\w*\W{1,3}\w*".join(re.escape(p) for p in parts)
    return len(re.findall(pat, text_l))


def _line_with(text: str, needle: str) -> str:
    i = text.lower().find(needle.lower())
    if i < 0:
        return needle
    a = text.rfind("\n", 0, i) + 1
    b = text.find("\n", i)
    return text[a: b if b > 0 else None].strip()[:300]


def _sentences(text: str) -> list[str]:
    paras = [p.strip() for p in re.split(r"\n+", text) if len(p.strip()) > 80 and not p.startswith(("---", "==="))]
    return paras


def extract(text: str) -> dict:
    out = {k: {"value": None, "quote": None} for k in _P}
    low = text.lower()

    # наименование: заголовок страницы или первая содержательная строка
    title = None
    m = re.search(r"Заголовок страницы:\s*(.+)", text)
    if m:
        title = re.split(r"\s[|—–-]\s|\s\|\s", m.group(1))[0].strip()
    if not title:  # первая строка первой страницы/слайда — обычно название продукта
        first = re.search(r"--- (?:стр\.|слайд) 1 ---\n\s*(.{5,150})", text)
        title = first.group(1).strip() if first else None
    if not title:
        title = next((ln.strip() for ln in text.splitlines()
                      if 5 <= len(ln.strip()) <= 150 and not ln.startswith(("---", "===", "Заголовок"))), None)
    if title:
        out["product_name"] = {"value": title[:300], "quote": title[:300]}
        short = re.split(r"[:—–(]", title)[0].strip()  # «АгроСкан-М: беспроводная…» → «АгроСкан-М»
        out["product_short_name"] = {"value": short[:60].rstrip(" ,.;:"), "quote": title[:300]}

    if m := ORG_RE.search(text):
        out["org_name"] = {"value": f"{m.group(1)} «{m.group(2).strip()}»", "quote": m.group(0)}
    if m := INN_RE.search(text):
        out["org_inn"] = {"value": m.group(1), "quote": m.group(0)}
    if m := SITE_RE.search(text):
        out["org_website"] = {"value": m.group(1).rstrip("."), "quote": m.group(0)}
    if m := TRL_RE.search(text):
        out["trl"] = {"value": int(m.group(1)), "quote": m.group(0)}
    if m := OKPD_RE.search(text):
        out["okpd2"] = {"value": m.group(1), "quote": m.group(0)}

    # регион: точное название субъекта или город
    for r in _P["region"]["enum"]:
        if r.lower() in low and len(r) > 6:
            out["region"] = {"value": r, "quote": _line_with(text, r)}
            break
    else:
        for city, reg in CITY_REGION.items():
            if re.search(r"\b(?:г\.\s*)?" + re.escape(city), low):
                out["region"] = {"value": reg, "quote": _line_with(text, city)}
                break

    # отрасль: наибольшее число попаданий ключевых слов
    scores = {ind: sum(_stem_hit(low, k) for k in kws) for ind, kws in INDUSTRY_KW.items()}
    best = max(scores, key=scores.get)
    if scores[best] >= 2:
        kw = next(k for k in INDUSTRY_KW[best] if _stem_hit(low, k))
        out["industry"] = {"value": best, "quote": _line_with(text, kw.split()[0])}

    for status, kws in STATUS_KW:
        hit = next((k for k in kws if k in low), None)
        if hit:
            out["dev_status"] = {"value": status, "quote": _line_with(text, hit)}
            break

    coop, coop_q = [], None
    for fmt, kws in COOP_KW.items():
        hit = next((k for k in kws if _stem_hit(low, k)), None)
        if hit:
            coop.append(fmt)
            coop_q = coop_q or _line_with(text, hit.split()[0])
    if coop:
        out["cooperation_format"] = {"value": coop, "quote": coop_q}

    # ТТХ: строки «параметр: значение» / «параметр | значение» с числом в значении
    # эффекты внедрений — те же строки, если параметр начинается со слова-эффекта
    params, effects, seen = [], [], set()
    for ln in text.splitlines():
        pm = PARAM_RE.match(ln)
        if not pm or pm.group(1).lower() in seen or SKIP_PARAM.search(pm.group(1)):
            continue
        seen.add(pm.group(1).lower())
        item = {"name": pm.group(1).strip(), "value": pm.group(2).strip()}
        (effects if EFFECT_PARAM.match(item["name"]) else params).append(item)
    if params:
        out["tech_params"] = {"value": params[:10], "quote": params[0]["name"]}
    if effects:
        out["deployment_effects"] = {"value": effects[:10], "quote": effects[0]["name"]}
    if m := re.search(r"\b(\d+|одно|два|три|пять)\s+(?:пилотн\w*\s+|успешн\w*\s+)?внедрени\w*", text, re.I):
        out["deployments_count"] = {"value": m.group(0), "quote": m.group(0)}

    # краткое описание: первый содержательный абзац (не пересказ — фрагмент текста)
    paras = _sentences(text)
    if paras:
        d = paras[0][:600]
        if len(paras[0]) > 600:
            d = d[: d.rfind(". ") + 1] or d
        out["description_short"] = {"value": d, "quote": d[:300]}
    return out


def _flat(v):
    if isinstance(v, list):
        return " | ".join(f"{x['name']}: {x['value']}" if isinstance(x, dict) else str(x) for x in v)
    return "" if v is None else str(v)


class DemoProvider(Provider):
    name = "demo"
    model = "rules-v0"

    def complete(self, system, user, schema):
        text = user.split("<<<", 1)[-1].rsplit(">>>", 1)[0]
        card = extract(text)
        flat = schema["properties"]["trl"]["properties"]["value"].get("type") == "string"
        if flat:
            card = {k: {"value": _flat(v["value"]), "quote": v["quote"] or ""} for k, v in card.items()}
        return json.dumps(card, ensure_ascii=False), {"prompt_tokens": len(user) // 4, "completion_tokens": 0}, {}
