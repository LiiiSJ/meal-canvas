-- Meal Canvas SQLite schema v1（sample 与 full 共用；双库同构）
-- 注意：journal_mode / synchronous 属于连接级设置，由 build.py（DELETE/OFF）与 API（WAL）各自设置。
-- 构建库不启用 WAL，保证 .tmp 是单文件，可原子替换。

CREATE TABLE meta (
    key   TEXT PRIMARY KEY,
    value TEXT
);

CREATE TABLE nutrient (
    id        INTEGER PRIMARY KEY,          -- FDC nutrient id
    nbr       TEXT NOT NULL UNIQUE,         -- 传统编号，跨数据集稳定键
    name_en   TEXT NOT NULL,
    unit_name TEXT NOT NULL,
    rank      REAL,
    name_zh   TEXT NOT NULL,
    unit_zh   TEXT NOT NULL,
    group_zh  TEXT NOT NULL,
    is_core   INTEGER NOT NULL,
    decimals  INTEGER NOT NULL
);

CREATE TABLE food (
    fdc_id             INTEGER PRIMARY KEY,
    data_type          TEXT NOT NULL,
    description_en     TEXT NOT NULL,
    name_zh            TEXT,
    zh_status          TEXT NOT NULL,
    zh_review_status   TEXT NOT NULL,
    brand_owner        TEXT,
    brand_name         TEXT,
    gtin_upc           TEXT,
    category_source    TEXT,
    category_code      TEXT,
    category_en        TEXT,
    category_zh        TEXT,
    publication_date   TEXT,
    source_dataset     TEXT NOT NULL,
    source_version     TEXT NOT NULL,
    serving_size       REAL,
    serving_unit       TEXT,
    household_serving  TEXT,
    ingredients_en     TEXT,
    is_default_library INTEGER NOT NULL,
    library_scope      TEXT NOT NULL,
    search_tokens      TEXT NOT NULL
);

CREATE TABLE food_nutrient (
    fdc_id             INTEGER NOT NULL,
    nutrient_id        INTEGER NOT NULL,
    amount             REAL,                -- NULL = 不可用；禁止用 0 表示缺失
    raw_amount         REAL,                -- CSV 原值，不做修正
    quality_flag       TEXT NOT NULL,
    origin_nutrient_id INTEGER,             -- 原始行营养编号（FNDDS 为传统编号）
    PRIMARY KEY (fdc_id, nutrient_id)
);

CREATE TABLE food_portion (
    id                  INTEGER PRIMARY KEY,
    fdc_id              INTEGER NOT NULL,
    amount              REAL,
    modifier            TEXT,
    portion_description TEXT,
    gram_weight         REAL,
    unit_name           TEXT,
    quality_flag        TEXT NOT NULL
);

CREATE TABLE food_alias (
    fdc_id        INTEGER NOT NULL,
    alias         TEXT NOT NULL,
    alias_type    TEXT NOT NULL,
    status        TEXT NOT NULL,
    review_status TEXT NOT NULL,
    PRIMARY KEY (fdc_id, alias, alias_type)
);

CREATE TABLE food_summary (
    fdc_id            INTEGER PRIMARY KEY,
    energy_kcal       REAL,
    protein_g         REAL,
    fat_g             REAL,
    carb_g            REAL,
    fiber_g           REAL,
    sugar_g           REAL,
    sodium_mg         REAL,
    known_core_count  INTEGER NOT NULL
);

-- 质量事件：只用于追溯，不参与营养计算
CREATE TABLE quality_event (
    id           INTEGER PRIMARY KEY,
    fdc_id       INTEGER NOT NULL,
    event_type   TEXT NOT NULL,
    nutrient_id  INTEGER,
    raw_amount   REAL,
    detail       TEXT
);

CREATE INDEX idx_food_data_type ON food(data_type);
CREATE INDEX idx_food_library_scope ON food(library_scope);
CREATE INDEX idx_food_default_category ON food(is_default_library, category_code);
CREATE INDEX idx_food_gtin ON food(gtin_upc);
CREATE INDEX idx_food_nutrient_fdc ON food_nutrient(fdc_id);
CREATE INDEX idx_food_nutrient_quality ON food_nutrient(quality_flag);
CREATE INDEX idx_food_portion_fdc ON food_portion(fdc_id);
CREATE INDEX idx_food_alias_fdc ON food_alias(fdc_id);
CREATE INDEX idx_food_summary_energy ON food_summary(energy_kcal, protein_g);
CREATE INDEX idx_quality_event_type ON quality_event(event_type);
CREATE INDEX idx_quality_event_fdc ON quality_event(fdc_id);

CREATE VIRTUAL TABLE food_fts USING fts5(
    fdc_id UNINDEXED,
    tokens,
    tokenize = 'unicode61'
);
