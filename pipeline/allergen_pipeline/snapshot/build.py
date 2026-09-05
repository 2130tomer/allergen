"""בניית תמונת המצב המקומית שהאפליקציה מורידה. ראו ADR-0003.

האפליקציה אינה שואלת את השרת בזמן סריקה, כי סופרמרקט הוא בדיוק המקום
עם הקליטה הגרועה. לכן כל מה שנדרש לחיפוש, לסריקה ולסינון נארז לקובץ
SQLite אחד, כולל אינדקס חיפוש בעברית.

תמונות ומידע מורחב אינם נכללים; הם נטענים מהרשת בעת הצורך.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from ..catalog import departments
from ..catalog.product import Product
from ..domain import allergens as allergen_catalog
from ..domain.resolution import ResolvedAllergens

SCHEMA_VERSION = 1

_SCHEMA = """
PRAGMA journal_mode = OFF;
PRAGMA synchronous = OFF;

CREATE TABLE meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE allergens (
    id        TEXT PRIMARY KEY,
    label_he  TEXT NOT NULL,
    parent_id TEXT REFERENCES allergens(id)
);

CREATE TABLE departments (
    id        TEXT PRIMARY KEY,
    label_he  TEXT NOT NULL,
    parent_id TEXT REFERENCES departments(id)
);

CREATE TABLE products (
    barcode              TEXT PRIMARY KEY,
    name                 TEXT NOT NULL,
    manufacturer         TEXT,
    department_id        TEXT NOT NULL REFERENCES departments(id),
    quantity             TEXT,
    unit                 TEXT,
    image_url            TEXT,
    image_source         TEXT,
    is_active            INTEGER NOT NULL DEFAULT 1,
    needs_review         INTEGER NOT NULL DEFAULT 0,
    has_allergen_data    INTEGER NOT NULL DEFAULT 0,
    -- קיימת רשימת רכיבים מלאה למוצר. נבדל מ-has_allergen_data: מוצר
    -- יכול להיות בעל רשימת רכיבים שלא נמצא בה אף אלרגן, וזה נתון
    -- שונה לחלוטין מהיעדר מידע. ראו INGREDIENTS_KNOWN_NO_MATCH בממשק.
    ingredients_known    INTEGER NOT NULL DEFAULT 0,
    allergens_observed_on TEXT
);

CREATE INDEX products_department ON products(department_id);

-- רמת האלרגן המוכרעת. שורה קיימת רק כשיש מידע; היעדר שורה הוא אין מידע
-- ולא לא מכיל.
CREATE TABLE product_allergens (
    barcode       TEXT NOT NULL REFERENCES products(barcode),
    allergen_id   TEXT NOT NULL REFERENCES allergens(id),
    level         TEXT NOT NULL,
    sources       TEXT NOT NULL,
    level_inferred INTEGER NOT NULL DEFAULT 0,
    inherited_from TEXT,
    observed_on   TEXT,
    PRIMARY KEY (barcode, allergen_id)
);

CREATE INDEX product_allergens_lookup ON product_allergens(allergen_id, level);

CREATE TABLE product_conflicts (
    barcode     TEXT NOT NULL REFERENCES products(barcode),
    allergen_id TEXT NOT NULL REFERENCES allergens(id),
    message     TEXT NOT NULL,
    PRIMARY KEY (barcode, allergen_id)
);

CREATE VIRTUAL TABLE products_fts USING fts5(
    barcode UNINDEXED,
    search_text,
    tokenize = 'unicode61 remove_diacritics 2'
);
"""


@dataclass(frozen=True)
class SnapshotStats:
    products: int
    with_allergen_data: int
    conflicts: int
    built_at: datetime

    @property
    def allergen_coverage(self) -> float:
        if self.products == 0:
            return 0.0
        return self.with_allergen_data / self.products


def build(
    path: Path,
    products: list[Product],
    resolved_by_barcode: dict[str, ResolvedAllergens],
    ingredients_known: set[str] | None = None,
) -> SnapshotStats:
    """כותב קובץ תמונת מצב חדש. קובץ קיים נדרס."""
    if path.exists():
        path.unlink()
    path.parent.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(path)
    try:
        connection.executescript(_SCHEMA)
        _write_reference_tables(connection)
        stats = _write_products(
            connection, products, resolved_by_barcode, ingredients_known or set()
        )
        _write_meta(connection, stats)
        connection.commit()
        # VACUUM אינו יכול לרוץ בתוך טרנזקציה, ולכן מבטלים את הניהול האוטומטי.
        connection.isolation_level = None
        connection.execute("VACUUM")
        return stats
    finally:
        connection.close()


def _write_reference_tables(connection: sqlite3.Connection) -> None:
    connection.executemany(
        "INSERT INTO allergens (id, label_he, parent_id) VALUES (?, ?, ?)",
        [
            (allergen.id, allergen.label_he, allergen.parent_id)
            for allergen in allergen_catalog.iter_allergens()
        ],
    )
    connection.executemany(
        "INSERT INTO departments (id, label_he, parent_id) VALUES (?, ?, ?)",
        [
            (department.id, department.label_he, department.parent_id)
            for department in departments.DEPARTMENTS.values()
        ],
    )


def _write_products(
    connection: sqlite3.Connection,
    products: list[Product],
    resolved_by_barcode: dict[str, ResolvedAllergens],
    known_ingredients: set[str],
) -> SnapshotStats:
    with_data = 0
    conflict_count = 0

    for product in products:
        resolved = resolved_by_barcode.get(product.barcode)
        has_data = bool(resolved and resolved.has_any_data)
        if has_data:
            with_data += 1

        observed = resolved.latest_observed_on if resolved else None
        connection.execute(
            """
            INSERT INTO products (
                barcode, name, manufacturer, department_id, quantity, unit,
                image_url, image_source, is_active, needs_review,
                has_allergen_data, ingredients_known, allergens_observed_on
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                product.barcode,
                product.canonical_name,
                product.manufacturer,
                product.department_id,
                product.quantity,
                product.unit,
                product.image.url if product.image else None,
                product.image.source_name if product.image else None,
                int(product.is_active),
                int(product.needs_review),
                int(has_data),
                int(product.barcode in known_ingredients),
                observed.isoformat() if observed else None,
            ),
        )
        connection.execute(
            "INSERT INTO products_fts (barcode, search_text) VALUES (?, ?)",
            (product.barcode, product.search_text),
        )

        if not resolved:
            continue

        for allergen_id, entry in resolved.by_allergen.items():
            if not entry.is_known:
                continue
            connection.execute(
                """
                INSERT INTO product_allergens (
                    barcode, allergen_id, level, sources, level_inferred,
                    inherited_from, observed_on
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    product.barcode,
                    allergen_id,
                    entry.level.value,
                    ",".join(source.value for source in entry.sources),
                    int(entry.level_inferred),
                    entry.inherited_from,
                    entry.observed_on.isoformat() if entry.observed_on else None,
                ),
            )

        for conflict in resolved.conflicts:
            connection.execute(
                """
                INSERT OR REPLACE INTO product_conflicts (barcode, allergen_id, message)
                VALUES (?, ?, ?)
                """,
                (product.barcode, conflict.allergen_id, conflict.message_he),
            )
            conflict_count += 1

    return SnapshotStats(
        products=len(products),
        with_allergen_data=with_data,
        conflicts=conflict_count,
        built_at=datetime.now(),
    )


def _write_meta(connection: sqlite3.Connection, stats: SnapshotStats) -> None:
    connection.executemany(
        "INSERT INTO meta (key, value) VALUES (?, ?)",
        [
            ("schema_version", str(SCHEMA_VERSION)),
            ("built_at", stats.built_at.isoformat(timespec="seconds")),
            ("product_count", str(stats.products)),
            ("with_allergen_data", str(stats.with_allergen_data)),
            ("conflict_count", str(stats.conflicts)),
        ],
    )
