"""בונה מרשם יצרני מזון ומשקאות מתוך הקטלוג.

המטרה מעשית ולא אנציקלופדית: לדעת לאיזה יצרנים כדאי לבנות מתאם
אלרגנים, ובאיזה סדר. יצרן שמכסה מאתיים מוצרים שווה מתאם; יצרן עם
מוצר אחד לא.

    python -m allergen_pipeline.map_manufacturers --top 40
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

from .catalog import manufacturers

DEFAULT_SNAPSHOT = Path("data/snapshots/allergen-snapshot.sqlite")
DEFAULT_OUTPUT = Path("data/manufacturers.json")


def load_names(snapshot: Path) -> tuple[list[tuple[str, int]], int]:
    """שמות יצרן וכמה מוצרי מזון לכל אחד."""
    connection = sqlite3.connect(snapshot)
    try:
        rows = connection.execute(
            "SELECT manufacturer, COUNT(*) FROM products"
            " WHERE manufacturer IS NOT NULL AND manufacturer <> ''"
            "   AND department_id <> 'non_food'"
            " GROUP BY manufacturer"
        ).fetchall()
        total = connection.execute(
            "SELECT COUNT(*) FROM products WHERE department_id <> 'non_food'"
        ).fetchone()[0]
    finally:
        connection.close()
    return [(name, count) for name, count in rows], total


def main(argv: list[str] | None = None) -> int:
    arguments = _parse_arguments(argv)

    if not arguments.snapshot.exists():
        print(f"אין תמונת מצב ב-{arguments.snapshot}", file=sys.stderr)
        return 1

    names, total_products = load_names(arguments.snapshot)
    registry = manufacturers.build_registry(names)
    groups = manufacturers.group_totals(registry)

    dropped = len(names) - len(registry)
    covered = sum(entry.product_count for entry in registry)

    print(f"מוצרי מזון בקטלוג: {total_products}")
    print(f"שמות יצרן גולמיים: {len(names)}")
    print(f"אחרי נרמול ואיחוד: {len(registry)}")
    print(f"ממלאי מקום שהושמטו: {dropped}")
    print(f"מוצרים עם יצרן אמיתי: {covered} ({covered / total_products:.0%})")

    print(f"\n=== {arguments.top} היצרנים הגדולים ===")
    for entry in registry[: arguments.top]:
        group = entry.group
        tag = f"  [{group.name_he}]" if group else ""
        variants = f"  ({len(entry.raw_names)} וריאנטים)" if len(entry.raw_names) > 1 else ""
        print(f"{entry.product_count:5d}  {entry.display_name}{tag}{variants}")

    print("\n=== קבוצות תאגידיות מזוהות ===")
    group_covered = 0
    for group, count in groups:
        group_covered += count
        status = _allergen_status(group)
        print(f"{count:5d}  {group.name_he:22s} {status}")
    print(
        f"\nהקבוצות המזוהות מכסות {group_covered} מוצרים "
        f"({group_covered / total_products:.0%} מהקטלוג)."
    )

    _write_registry(arguments.output, registry, groups, total_products)
    print(f"\nהמרשם נכתב ל-{arguments.output}")
    return 0


def _allergen_status(group: manufacturers.ManufacturerGroup) -> str:
    if group.publishes_allergens is True:
        return "מפרסם אלרגנים"
    if group.publishes_allergens is False:
        return "לא מפרסם"
    return "לא נבדק"


def _write_registry(
    path: Path,
    registry: list[manufacturers.ManufacturerEntry],
    groups: list[tuple[manufacturers.ManufacturerGroup, int]],
    total_products: int,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "total_food_products": total_products,
        "groups": [
            {
                "id": group.id,
                "name_he": group.name_he,
                "website": group.website,
                "publishes_allergens": group.publishes_allergens,
                "notes": group.notes,
                "product_count": count,
            }
            for group, count in groups
        ],
        "manufacturers": [
            {
                "display_name": entry.display_name,
                "normalized": entry.normalized,
                "product_count": entry.product_count,
                "group_id": entry.group_id,
                "raw_names": sorted(entry.raw_names),
            }
            for entry in registry
        ],
    }
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _parse_arguments(argv: list[str] | None) -> argparse.Namespace:
    argument_parser = argparse.ArgumentParser(prog="map_manufacturers")
    argument_parser.add_argument("--snapshot", type=Path, default=DEFAULT_SNAPSHOT)
    argument_parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    argument_parser.add_argument("--top", type=int, default=40)
    return argument_parser.parse_args(argv)


if __name__ == "__main__":
    raise SystemExit(main())
