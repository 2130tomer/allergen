-- מסד הנתונים של השרת. תמונת המצב שהאפליקציה מורידה נגזרת ממנו.
--
-- ההבדל המהותי מהתמונה המקומית: כאן נשמרות כל הקביעות מכל המקורות,
-- כולל סותרות, עם מקור ותאריך. ההכרעה ביניהן מחושבת ואינה מאוחסנת
-- כערך יחיד. ראו ADR-0004.

CREATE TABLE IF NOT EXISTS retailers (
    id          TEXT PRIMARY KEY,
    name_he     TEXT NOT NULL,
    portal      TEXT NOT NULL,
    base_url    TEXT NOT NULL,
    username    TEXT,
    priority    INTEGER NOT NULL DEFAULT 99
);

CREATE TABLE IF NOT EXISTS departments (
    id          TEXT PRIMARY KEY,
    label_he    TEXT NOT NULL,
    parent_id   TEXT REFERENCES departments(id)
);

CREATE TABLE IF NOT EXISTS allergens (
    id          TEXT PRIMARY KEY,
    label_he    TEXT NOT NULL,
    parent_id   TEXT REFERENCES allergens(id)
);

CREATE TABLE IF NOT EXISTS products (
    barcode         TEXT PRIMARY KEY,
    canonical_name  TEXT NOT NULL,
    manufacturer    TEXT,
    department_id   TEXT NOT NULL REFERENCES departments(id),
    quantity        TEXT,
    unit            TEXT,
    search_text     TEXT NOT NULL DEFAULT '',
    first_seen_on   DATE,
    last_seen_on    DATE,
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    -- נדלק בחשד למיחזור ברקוד או בשינוי מתכון. מקפיא שיוך אלרגנים ישן.
    needs_review    BOOLEAN NOT NULL DEFAULT FALSE,
    review_reason   TEXT,
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS products_department_idx ON products(department_id);
CREATE INDEX IF NOT EXISTS products_active_idx ON products(is_active);

-- שם שרשת נתנה למוצר. אינו מוצג; נכנס לאינדקס החיפוש בלבד.
CREATE TABLE IF NOT EXISTS product_aliases (
    barcode     TEXT NOT NULL REFERENCES products(barcode) ON DELETE CASCADE,
    alias       TEXT NOT NULL,
    retailer_id TEXT REFERENCES retailers(id),
    PRIMARY KEY (barcode, alias)
);

CREATE TABLE IF NOT EXISTS product_offers (
    barcode      TEXT NOT NULL REFERENCES products(barcode) ON DELETE CASCADE,
    retailer_id  TEXT NOT NULL REFERENCES retailers(id),
    retailer_sku TEXT,
    raw_name     TEXT NOT NULL,
    observed_on  DATE NOT NULL,
    PRIMARY KEY (barcode, retailer_id)
);

CREATE TABLE IF NOT EXISTS product_ingredients (
    barcode       TEXT PRIMARY KEY REFERENCES products(barcode) ON DELETE CASCADE,
    raw_text      TEXT NOT NULL,
    fingerprint   TEXT NOT NULL,
    source        TEXT NOT NULL,
    source_ref    TEXT,
    observed_on   DATE NOT NULL
);

-- קביעה בודדת ממקור אחד. מוצר יכול לשאת כמה קביעות סותרות לאותו אלרגן.
CREATE TABLE IF NOT EXISTS allergen_claims (
    id              BIGSERIAL PRIMARY KEY,
    barcode         TEXT NOT NULL REFERENCES products(barcode) ON DELETE CASCADE,
    allergen_id     TEXT NOT NULL REFERENCES allergens(id),
    level           TEXT NOT NULL CHECK (level IN ('contains', 'may_contain', 'absent')),
    source          TEXT NOT NULL,
    source_ref      TEXT,
    observed_on     DATE NOT NULL,
    -- נכון כשהרמה נגזרה מפירוק רשימה שטוחה ולא נאמרה במפורש במקור.
    level_inferred  BOOLEAN NOT NULL DEFAULT FALSE,
    retired_at      TIMESTAMPTZ,
    UNIQUE (barcode, allergen_id, source, observed_on)
);

-- רק מקור יצרן רשאי לקבוע שאלרגן נעדר. ראו ADR-0002.
ALTER TABLE allergen_claims
    DROP CONSTRAINT IF EXISTS allergen_claims_absence_requires_manufacturer;
ALTER TABLE allergen_claims
    ADD CONSTRAINT allergen_claims_absence_requires_manufacturer
    CHECK (level <> 'absent' OR source = 'manufacturer');

CREATE INDEX IF NOT EXISTS allergen_claims_barcode_idx
    ON allergen_claims(barcode) WHERE retired_at IS NULL;

CREATE TABLE IF NOT EXISTS product_images (
    barcode        TEXT PRIMARY KEY REFERENCES products(barcode) ON DELETE CASCADE,
    stored_url     TEXT NOT NULL,
    source_url     TEXT NOT NULL,
    source_name    TEXT NOT NULL,
    fetched_on     DATE NOT NULL,
    -- מדיניות ההסרה של ADR-0005: בקשת יצרן מסירה את התמונה מיידית.
    removed_at     TIMESTAMPTZ,
    removal_reason TEXT
);

-- תיעוד ריצות. שקט של מתאם הוא אירוע ולא היעדר אירוע.
CREATE TABLE IF NOT EXISTS adapter_runs (
    id               BIGSERIAL PRIMARY KEY,
    adapter_id       TEXT NOT NULL,
    started_at       TIMESTAMPTZ NOT NULL,
    finished_at      TIMESTAMPTZ,
    rows_seen        INTEGER NOT NULL DEFAULT 0,
    accepted         BOOLEAN NOT NULL DEFAULT FALSE,
    rejection_reason TEXT
);

CREATE INDEX IF NOT EXISTS adapter_runs_latest_idx
    ON adapter_runs(adapter_id, started_at DESC);

-- תרומות משתמשים ממתינות. אינן נכנסות לתמונת המצב לפני עיבוד.
CREATE TABLE IF NOT EXISTS label_submissions (
    id            BIGSERIAL PRIMARY KEY,
    barcode       TEXT NOT NULL,
    image_path    TEXT NOT NULL,
    submitted_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    processed_at  TIMESTAMPTZ,
    outcome       TEXT
);
