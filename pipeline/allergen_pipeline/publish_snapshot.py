"""העתקת תמונת המצב לתוך נכסי האפליקציה.

הצינור בונה ל-data/snapshots, והאפליקציה נשלחת עם עותק ארוז. ההפרדה
מכוונת: תמונת מצב שנבנתה זה עתה אינה נכנסת אוטומטית לאפליקציה, אלא רק
אחרי בדיקה מפורשת שהיא לא ריקה ולא קטנה מדי.

    python -m allergen_pipeline.publish_snapshot
"""

from __future__ import annotations

import argparse
import shutil
import sqlite3
import sys

from .snapshot.build import SCHEMA_VERSION
from pathlib import Path

DEFAULT_SOURCE = Path("data/snapshots/allergen-snapshot.sqlite")
DEFAULT_TARGET = Path("../app/assets/allergen-snapshot.sqlite")

# מתחת לזה, תמונת המצב כנראה תוצר של ריצה שבורה ואין להעביר אותה.
MIN_PRODUCTS = 500


def inspect(path: Path) -> tuple[int, int, str]:
    """מחזיר מספר מוצרים, מספר בעלי מידע אלרגנים, ותאריך בנייה."""
    connection = sqlite3.connect(path)
    try:
        if connection.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise ValueError("Snapshot integrity check failed")
        if connection.execute("PRAGMA foreign_key_check").fetchone() is not None:
            raise ValueError("Snapshot foreign key check failed")
        meta = dict(connection.execute("SELECT key, value FROM meta").fetchall())
        if int(meta.get("schema_version", 0)) != SCHEMA_VERSION:
            raise ValueError("Unsupported snapshot schema")
        products = connection.execute("SELECT COUNT(*) FROM products").fetchone()[0]
        with_data = connection.execute(
            "SELECT COUNT(*) FROM products WHERE has_allergen_data = 1"
        ).fetchone()[0]
    finally:
        connection.close()
    return products, with_data, meta.get("built_at", "לא ידוע")


def main(argv: list[str] | None = None) -> int:
    arguments = _parse_arguments(argv)

    if not arguments.source.exists():
        print(f"אין תמונת מצב ב-{arguments.source}", file=sys.stderr)
        return 1

    try:
        products, with_data, built_at = inspect(arguments.source)
    except (sqlite3.Error, ValueError) as error:
        print(str(error), file=sys.stderr)
        return 1
    coverage = with_data / products if products else 0.0

    print(f"מקור: {arguments.source}")
    print(f"  מוצרים: {products}")
    print(f"  עם מידע אלרגנים: {with_data} ({coverage:.1%})")
    print(f"  נבנתה: {built_at}")

    if products < MIN_PRODUCTS and not arguments.force:
        print(
            f"\nרק {products} מוצרים, מתחת לסף {MIN_PRODUCTS}. "
            "לא מעביר. השתמש ב---force אם זה מכוון.",
            file=sys.stderr,
        )
        return 2

    if not arguments.force:
        if with_data == 0:
            print("Refusing to publish a snapshot with no allergen data", file=sys.stderr)
            return 2
        if arguments.target.exists():
            # The previous schema may be older: compare its counts directly.
            # sqlite3.connect כ-context manager מנהל טרנזקציה ואינו סוגר
            # את החיבור. החיבור שנשאר פתוח נועל את קובץ היעד, ובחלונות
            # os.replace על קובץ נעול נכשל ב-PermissionError. בלינוקס זה
            # עובר, ולכן הבאג מתגלה רק כאן.
            previous = sqlite3.connect(arguments.target)
            try:
                old_products = previous.execute("SELECT COUNT(*) FROM products").fetchone()[0]
                old_data = previous.execute(
                    "SELECT COUNT(*) FROM products WHERE has_allergen_data = 1"
                ).fetchone()[0]
            finally:
                previous.close()
            if products < old_products * 0.8 or with_data < old_data * 0.8:
                print("Refusing a drop above 20% in products or allergen coverage", file=sys.stderr)
                return 2

    arguments.target.parent.mkdir(parents=True, exist_ok=True)
    staging = arguments.target.with_suffix(arguments.target.suffix + ".tmp")
    try:
        shutil.copy2(arguments.source, staging)
        inspect(staging)
        staging.replace(arguments.target)
    finally:
        staging.unlink(missing_ok=True)
    size_mb = arguments.target.stat().st_size / (1024 * 1024)
    print(f"\nהועתק אל {arguments.target} ({size_mb:.1f}MB)")
    return 0


def _parse_arguments(argv: list[str] | None) -> argparse.Namespace:
    argument_parser = argparse.ArgumentParser(prog="publish_snapshot")
    argument_parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    argument_parser.add_argument("--target", type=Path, default=DEFAULT_TARGET)
    argument_parser.add_argument("--force", action="store_true")
    return argument_parser.parse_args(argv)


if __name__ == "__main__":
    raise SystemExit(main())
