-- Технотека.ИИ — хранение прототипа (B03). SQLite в режиме WAL; файлы — на диске в files/<card_id>/.
-- Карточка хранится одним JSON (values_json) по card_schema_v0.json: смена шаблона не требует миграций.

PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

-- Приглашение организации на пилот. Ссылка вида https://<стенд>/?t=<token>.
-- plan — порядок двух карточек для контрбалансировки: ["manual","ai"] или ["ai","manual"].
CREATE TABLE IF NOT EXISTS invites (
    id          INTEGER PRIMARY KEY,
    token       TEXT    NOT NULL UNIQUE,
    org_label   TEXT    NOT NULL,                 -- как мы называем организацию внутри (не из карточки)
    plan        TEXT    NOT NULL DEFAULT '["ai"]',
    created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS cards (
    id             INTEGER PRIMARY KEY,
    invite_id      INTEGER NOT NULL REFERENCES invites(id),
    mode           TEXT    NOT NULL CHECK (mode IN ('ai', 'manual')),
    status         TEXT    NOT NULL DEFAULT 'draft'
                   CHECK (status IN ('draft', 'processing', 'ready', 'submitted', 'accepted', 'returned')),
    schema_version TEXT    NOT NULL,
    values_json    TEXT    NOT NULL DEFAULT '{}', -- {поле: значение} — то, что видит и правит пользователь
    ai_json        TEXT,                          -- ExtractionResult целиком (значения ИИ, цитаты, токены, ошибки)
    created_at     TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at     TEXT    NOT NULL DEFAULT (datetime('now')),
    submitted_at   TEXT
);
CREATE INDEX IF NOT EXISTS cards_status ON cards(status);

CREATE TABLE IF NOT EXISTS files (
    id          INTEGER PRIMARY KEY,
    card_id     INTEGER NOT NULL REFERENCES cards(id) ON DELETE CASCADE,
    name        TEXT    NOT NULL,                 -- исходное имя
    path        TEXT    NOT NULL,                 -- files/<card_id>/<file_id>/<исходное имя> (имя видно модели и в предупреждениях)
    mime        TEXT    NOT NULL,
    size        INTEGER NOT NULL,
    sha256      TEXT    NOT NULL,
    uploaded_at TEXT    NOT NULL DEFAULT (datetime('now'))
);

-- Журнал действий для замера времени (показатель 1) и разбора UX.
-- type: card_opened | files_uploaded | extraction_started | extraction_done | field_changed | submitted
CREATE TABLE IF NOT EXISTS events (
    id         INTEGER PRIMARY KEY,
    card_id    INTEGER NOT NULL REFERENCES cards(id) ON DELETE CASCADE,
    type       TEXT    NOT NULL,
    field      TEXT,                              -- для field_changed: ключ поля
    client_ts  TEXT    NOT NULL,                  -- время браузера (ISO 8601)
    server_ts  TEXT    NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS events_card ON events(card_id, type);

-- Решение модератора по чек-листу F01 (показатель 2: доля принятых с первого раза).
CREATE TABLE IF NOT EXISTS moderation (
    id             INTEGER PRIMARY KEY,
    card_id        INTEGER NOT NULL REFERENCES cards(id) ON DELETE CASCADE,
    moderator      TEXT    NOT NULL,
    checklist_json TEXT    NOT NULL,              -- {пункт чек-листа: true/false}
    verdict        TEXT    NOT NULL CHECK (verdict IN ('accepted', 'returned')),
    comment        TEXT,
    created_at     TEXT    NOT NULL DEFAULT (datetime('now'))
);

-- Время заполнения карточки: от первого открытия до ПЕРВОЙ отправки (ожидание ответа модели входит;
-- доработка после возврата модератором в КПЭ «время» не входит — она учитывается в «принята с первого раза»).
CREATE VIEW IF NOT EXISTS card_timing AS
SELECT c.id AS card_id, c.mode, c.invite_id,
       (julianday(MIN(CASE WHEN e.type = 'submitted'   THEN e.client_ts END)) -
        julianday(MIN(CASE WHEN e.type = 'card_opened' THEN e.client_ts END))) * 1440 AS minutes
FROM cards c JOIN events e ON e.card_id = c.id
GROUP BY c.id;

-- Принята ли карточка с первой модерации.
CREATE VIEW IF NOT EXISTS first_pass AS
SELECT card_id, verdict = 'accepted' AS accepted_first
FROM moderation m
WHERE m.id = (SELECT MIN(id) FROM moderation WHERE card_id = m.card_id);
