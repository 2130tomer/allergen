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
from pathlib import Path

DEFAULT_SOURCE = Path("data/snapshots/allergen-snapshot.sqlite")
DEFAULT_TARGET = Path("../app/assets/allergen-snapshot.sqlite")

# מתחת לזה, תמונת המצב כנראה תוצר של ריצה שבורה ואין להעביר אותה.
MIN_PRODUCTS = 500


def inspect(path: Path) -> tuple[int, int, str]:
    """מחזיר מספר מוצרים, מספר בעלי מידע אלרגנים, ותאריך בנייה."""
    connection = sqlite3.connect(path)
    try:
        meta = dict(connection.execute("SELECT key, value FROM meta").fetchall())
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

    products, with_data, built_at = inspect(arguments.source)
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

    arguments.target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(arguments.source, arguments.target)
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
