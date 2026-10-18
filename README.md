# Технотека.ИИ — прототип и рабочие материалы

## Прототип: запуск за 3 минуты

Локально (Python 3.11+, Node 20+):

```bash
pip install -r requirements.txt
cd frontend && npm ci && npm run build && cd ..        # фронт собирается в backend/static
python -m demo.make_demo                                # демо-материалы (вымышленная организация)
LLM_PROVIDER=demo ADMIN_PASSWORD=secret uvicorn backend.main:app --port 8000
python -m backend.cli invite "НИИ Пример" ai,manual     # → ссылка-приглашение для организации
```

* Организация: открыть ссылку-приглашение → «Начать» → загрузить файлы из `demo/agrosensor/` → «Заполнить автоматически».
* Модератор: http://localhost:8000/admin (admin / пароль из ADMIN_PASSWORD) — карточки, чек-лист, выгрузка в Excel.
* Приглашения — только из консоли: `python -m backend.cli invite …`, список — `python -m backend.cli invites`.
* API с документацией: http://localhost:8000/api/docs

Разработка фронта с горячей перезагрузкой: бэкенд как выше + `cd frontend && npm run dev` → http://localhost:5173.

**Провайдер извлечения** — переменная `LLM_PROVIDER`:

| значение | что делает |
| --- | --- |
| `demo` | правила и регулярные выражения, без ключей: ИНН, сайт, юрлицо, регион, отрасль, ТТХ. Для показа и разработки фронта, **не модель** |
| `yandex` / `gigachat` | настоящее извлечение (ключи — ниже, раздел B02) |
| `mock` | заведомо ложный ответ («ООО «Выдумка»») — для тестов проверки цитат |

**На ВМ** (docker compose + Caddy с автоматическим HTTPS):

```bash
cp .env.example .env      # DOMAIN, PUBLIC_URL, ADMIN_PASSWORD, LLM_PROVIDER и ключи
docker compose up -d --build
docker compose exec app python -m backend.cli invite "НИИ Пример" ai,manual
```

Данные — в `./var` (база SQLite + загруженные файлы): эту папку и бэкапить. Если Docker Hub с ВМ
недоступен, укажите зеркало реестра в `/etc/docker/daemon.json` (`"registry-mirrors": [...]`).

**Тесты:** `pytest -q tests` — сквозной сценарий через API; `python tests/e2e_browser.py <ссылка> --admin admin:<пароль>` —
тот же сценарий в браузере (Playwright) со скриншотами.

### Как устроен сценарий пилота

1. Команда создаёт приглашение из консоли с порядком карточек (`ai,manual` или `manual,ai` — чередовать для контрбалансировки).
2. Организация по ссылке создаёт карточки в этом порядке. Карточка с ИИ: загрузка → извлечение в фоне (статус
   `processing`, фронт опрашивает раз в 2 с) → форма с метками «ИИ», цитатами и предупреждением «проверьте», если
   цитата не найдена в тексте. Ручная карточка — та же форма без автозаполнения.
3. Автосохранение раз в 0,8 с после правки; ошибки формата показываются сразу, обязательные поля — при отправке.
4. Фронт пишет события (открытие, загрузка, правки полей, отправка) → время заполнения = от `card_opened` до `submitted`.
5. Модератор проверяет по чек-листу → принять / вернуть с комментарием (организация видит комментарий, правит, отправляет снова).
6. «Выгрузка для КПЭ»: лист «Карточки» (время, принята с первого раза, заполненность), «Поля ИИ» (что предложил ИИ и
   исправил ли пользователь — для оценки точности на живых данных), «События».

## Состав

```
schema/card_schema_v0.json   A02  шаблон карточки v0: 22 поля MVP (15 обязательных), единый источник правды
tools/card.py                     схема → LLM-схема (full/flat), разбор ответа, проверка формата и цитат
tools/doc_text.py                 PDF/DOCX/PPTX → текст с метками страниц/слайдов
tools/prompt.py                   промпт извлечения v0 (основа для D02)
b02/compare.py, providers.py B02  прогон провайдеров на одних документах → review.xlsx
backend/openapi.yaml         B03  контракт фронт ↔ бэк (OpenAPI 3.1)
backend/schema.sql           B03  SQLite: приглашения, карточки, файлы, события, модерация + расчёт времени
backend/main.py, db.py, cli.py    бэкенд прототипа (FastAPI) по openapi.yaml; cli — приглашения из консоли
frontend/                         React + Vite + TypeScript + RJSF (Ant Design): форма строится из схемы карточки
ml/extract.py                B03  контракт бэк ↔ ML: extract_card(files) → ExtractionResult (LLM_PROVIDER=demo|yandex|gigachat|mock)
ml/heuristic.py                   демо-извлечение правилами (без LLM)
demo/make_demo.py                 демо-комплект «Агросенсор» (вымышленный): PDF-презентация + DOCX
tests/                            test_api.py (pytest), e2e_browser.py (Playwright)
Dockerfile, docker-compose.yml, Caddyfile, .env.example    развёртывание на ВМ
c02/sources.csv, download.py C02  список 30 комплектов открытых материалов и их загрузка в data/raw
c04/gold.py                  C04  бланк эталонной разметки (Excel) ⇄ JSON, с проверкой цитат
c04/split.py                 C04  манифест комплектов и разбиение dev/test (стратифицированное, seed)
```

## Установка

```bash
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
```

## Структура данных

```
data/raw/TT-001/…            материалы комплекта (1+ файлов одной разработки)
data/manifest.csv            комплекты + источник (egisu | fips | mtk_site | respondent | vitrina)
data/split.csv               dev / test — после фиксации не перегенерировать
data/gold_xlsx/TT-001.xlsx   бланк разметки
data/gold/TT-001.json        эталон
```

## B02 — сравнение провайдеров

```bash
# Yandex AI Studio (сервисный аккаунт с API-ключом)
export YANDEX_API_KEY=… YANDEX_FOLDER_ID=…
export YANDEX_MODEL=…   # часть URI после gpt://<folder>/ — для Alice AI LLM (128k) взять из консоли AI Studio;
                        # по умолчанию yandexgpt/latest (32k — длинные документы могут не влезть)
# GigaChat (ключ авторизации из личного кабинета)
export GIGACHAT_AUTH_KEY=… GIGACHAT_SCOPE=GIGACHAT_API_CORP   # PERS — для физлица
export GIGACHAT_CA_BUNDLE=/path/russian_trusted_root_ca.pem   # сертификат НУЦ Минцифры
# Цены, ₽ за 1000 токенов (из тарифов) — для строки «Стоимость прогона»
export PRICE_YANDEX_IN=… PRICE_YANDEX_OUT=… PRICE_GIGACHAT_IN=… PRICE_GIGACHAT_OUT=…

python -m b02.compare --docs data/b02_docs --providers yandex,gigachat --out out/b02
python -m b02.compare --docs data/b02_docs --providers mock --out out/b02_test   # проверка без сети
```

`--mode auto` (по умолчанию): сначала полная JSON-схема (типы, enum, null), при отказе провайдера —
плоская (все значения строками). В сводке видно, какой режим сработал.

Дальше на листе «Оценка» в review.xlsx проставить по каждому полю 1 / 0 / x — сводка посчитается сама.

Проверить на первом запросе: URI модели Яндекса и формат ответа GigaChat v2 (парсер берёт первый
JSON-текст ассистента; сырой ответ сохраняется в out/b02/raw/).

## C02 — сбор комплектов

`c02/sources.csv` — 30 комплектов (34 файла): 18 с сайтов технологических компаний, 7 патентов,
5 разработок НИИ. Колонки region/industry — справка для сборщика, не эталон.

```bash
python -m c02.download --out data/raw --manifest data/manifest.csv
```

Повторный запуск докачивает только недостающее. В отчёте видно, сколько текста извлеклось из каждого
комплекта: страницы, которые собираются скриптами в браузере, дадут почти пустой текст — такие
сохранить вручную (браузер → «Сохранить как» или печать в PDF) в ту же папку.

## C04 — разметка

```bash
python -m c04.split scan data/raw --out data/manifest.csv        # не нужно, если манифест сделал c02.download
python -m c04.split split data/manifest.csv --dev 10 --force-dev <5 комплектов B02 через запятую> --out data/split.csv
python -m c04.gold template TT-001 --out data/gold_xlsx/TT-001.xlsx
python -m c04.gold template TT-001 --prefill out/b02/raw/TT-001__yandex.json --out …  # с предразметкой
python -m c04.gold import data/gold_xlsx/TT-001.xlsx --source data/raw/TT-001 --out data/gold/TT-001.json
```

C07 (+20 комплектов): `split … --existing data/split.csv` — dev не меняется, новые уходят в test.
