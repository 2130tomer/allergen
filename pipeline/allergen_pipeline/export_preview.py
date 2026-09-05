"""מייצא מקבע קטן לבנייה ל-web, מתוך תמונת המצב.

הבנייה ל-web היא כלי לבדיקת ממשק ואינה האפליקציה: אין בדפדפן SQLite,
ולכן המסכים נטענים ממקבע JSON. עד כה המקבע נוצר ידנית פעם אחת, וכתוצאה
מכך הוא הלך והתיישן ביחס למסד — מצב חדש שנוסף לצינור פשוט לא הופיע
במסך הבדיקה.

הבחירה כאן אינה אקראית במכוון. מקבע אקראי היה מלא מוצרים משעממים
שמצבם זהה, ובדיקת ממשק על נתונים כאלה אינה בודקת דבר. לכן נבחרים
מוצרים שמדגימים כל אחד מהמצבים שהממשק אמור להבדיל ביניהם, ובראשם
הצהרות "ללא" וסתירות בין מקורות, שהם המצבים הנדירים והחשובים.

    python -m allergen_pipeline.export_preview
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path

DEFAULT_SNAPSHOT = Path("data/snapshots/allergen-snapshot.sqlite")
DEFAULT_OUTPUT = Path("../app/src/db/fixtures/preview.json")

# כמה מוצרים לקחת מכל קטגוריית עניין.
PER_BUCKET = 14


def _rows(cursor: sqlite3.Cursor, sql: str, *args) -> list[sqlite3.Row]:
    return list(cursor.execute(sql, args))


def pick_barcodes(cursor: sqlite3.Cursor) -> list[str]:
    """בוחר מוצרים שמדגימים את כל המצבים שהממשק מבדיל ביניהם."""
    buckets: list[tuple[str, str]] = [
        (
            "הצהרת ללא",
            """select distinct p.barcode from products p
               join product_allergens a on a.barcode = p.barcode
               where a.level = 'absent' and p.department_id <> 'non_food'
               limit ?""",
        ),
        (
            "סתירה בין מקורות",
            """select distinct barcode from product_conflicts limit ?""",
        ),
        (
            "מכיל ועלול להכיל",
            """select p.barcode from products p
               join product_allergens a on a.barcode = p.barcode
               where a.level = 'may_contain' and p.department_id <> 'non_food'
               group by p.barcode having count(*) >= 2 limit ?""",
        ),
        (
            "מכיל בלבד",
            """select p.barcode from products p
               join product_allergens a on a.barcode = p.barcode
               where a.level = 'contains' and p.department_id <> 'non_food'
               group by p.barcode limit ?""",
        ),
        (
            "בלי מידע כלל",
            """select barcode from products
               where has_allergen_data = 0 and department_id <> 'non_food'
               limit ?""",
        ),
    ]

    chosen: list[str] = []
    seen: set[str] = set()
    for label, sql in buckets:
        found = [row[0] for row in _rows(cursor, sql, PER_BUCKET)]
        added = [b for b in found if b not in seen]
        seen.update(added)
        chosen.extend(added)
        print(f"  {label:22s} {len(added)}")
    return chosen


def main(argv: list[str] | None = None) -> int:
    arguments = _parse_arguments(argv)
    connection = sqlite3.connect(arguments.snapshot)
    connection.row_factory = sqlite3.Row
    cursor = connection.cursor()

    print("בוחר מוצרים למקבע:")
    barcodes = pick_barcodes(cursor)
    placeholders = ",".join("?" for _ in barcodes)

    products = [
        {
            "barcode": row["barcode"],
            "name": row["name"],
            "manufacturer": row["manufacturer"],
            "departmentId": row["department_id"],
            "quantity": row["quantity"],
            "unit": row["unit"],
            "imageUrl": row["image_url"],
            "imageSource": row["image_source"],
            "isActive": bool(row["is_active"]),
            "needsReview": bool(row["needs_review"]),
            "hasAllergenData": bool(row["has_allergen_data"]),
            "ingredientsKnown": bool(row["ingredients_known"]),
            "allergensObservedOn": row["allergens_observed_on"],
        }
        for row in _rows(
            cursor,
            f"select * from products where barcode in ({placeholders})",
            *barcodes,
        )
    ]

    allergens: dict[str, dict] = {}
    for row in _rows(
        cursor,
        f"select * from product_allergens where barcode in ({placeholders})",
        *barcodes,
    ):
        record = allergens.setdefault(
            row["barcode"], {"levels": {}, "sources": [], "inferred": []}
        )
        record["levels"][row["allergen_id"]] = row["level"]
        for source in (row["sources"] or "").split(","):
            if source and source not in record["sources"]:
                record["sources"].append(source)
        if row["level_inferred"]:
            record["inferred"].append(row["allergen_id"])

    conflicts: dict[str, list[dict]] = {}
    for row in _rows(
        cursor,
        f"select * from product_conflicts where barcode in ({placeholders})",
        *barcodes,
    ):
        conflicts.setdefault(row["barcode"], []).append(
            {"allergenId": row["allergen_id"], "message": row["message"]}
        )

    departments = [
        {"id": row["id"], "labelHe": row["label_he"], "parentId": row["parent_id"]}
        for row in _rows(cursor, "select * from departments")
    ]

    payload = {
        "products": products,
        "allergens": allergens,
        "departments": departments,
        "conflicts": conflicts,
    }
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    # בלי BOM. הגרסה הקודמת נכתבה עם BOM ולא נפתחה בכלים סטנדרטיים.
    arguments.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8"
    )

    print(f"\nנכתבו {len(products)} מוצרים ל-{arguments.output}")
    print(f"  עם קביעות אלרגן: {len(allergens)}")
    print(f"  עם סתירות: {len(conflicts)}")
    return 0


def _parse_arguments(argv: list[str] | None) -> argparse.Namespace:
    argument_parser = argparse.ArgumentParser(prog="export_preview")
    argument_parser.add_argument("--snapshot", type=Path, default=DEFAULT_SNAPSHOT)
    argument_parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return argument_parser.parse_args(argv)


if __name__ == "__main__":
    raise SystemExit(main())
