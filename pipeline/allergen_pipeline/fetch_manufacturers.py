"""מוריד דפי מוצר של יצרנים ושומר את קביעות האלרגן שלהם.

התוצאה נשמרת לקובץ JSON שהצינור הראשי קורא, כדי שהעשרה מהיצרן לא
תדרוש רשת בכל בנייה מחדש של הקטלוג.

    python -m allergen_pipeline.fetch_manufacturers
"""

from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

from .ingredients.mapping import IngredientAllergenMap
from .sources.manufacturers import base as manufacturer_base
from .sources.manufacturers import osem_client

DEFAULT_SEED = (
    Path(__file__).parent / "sources" / "manufacturers" / "data" / "osem_products.txt"
)
DEFAULT_OUTPUT = Path("data/cache/manufacturer_claims.json")


def main(argv: list[str] | None = None) -> int:
    arguments = _parse_arguments(argv)
    urls = osem_client.load_seed_urls(arguments.seed)
    if not urls:
        print(f"אין כתובות ב-{arguments.seed}")
        return 1

    print(f"מוריד {len(urls)} דפי מוצר מאסם-נסטלה.")
    products, stats = osem_client.crawl(urls, verbose=not arguments.quiet)

    ingredient_map = IngredientAllergenMap.load()
    observed_on = date.today()
    records: dict[str, dict] = {}

    for product in products:
        claims = manufacturer_base.to_claims(product, ingredient_map, observed_on)
        if not claims:
            continue
        records[product.barcode] = {
            "barcode": product.barcode,
            "name": product.product_name,
            "page_url": product.page_url,
            "image_url": product.image_url,
            "ingredients_text": product.ingredients_text,
            "observed_on": observed_on.isoformat(),
            "claims": [
                {
                    "allergen_id": claim.allergen_id,
                    "level": claim.level.value,
                    "level_inferred": claim.level_inferred,
                }
                for claim in claims
            ],
        }

    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(
        json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(f"\n  נשאלו: {stats.requested}")
    print(f"  התקבלו: {stats.fetched}")
    print(f"  עם ברקוד ודאי: {stats.linkable}")
    print(f"  עם הצהרת אלרגנים: {stats.with_allergens}")
    print(f"  כשלים: {stats.failures}")
    print(f"\nנשמרו {len(records)} מוצרים ל-{arguments.output}")

    for barcode, record in list(records.items())[:5]:
        levels = ", ".join(
            f"{claim['allergen_id']}={claim['level']}" for claim in record["claims"]
        )
        print(f"  {barcode}  {record['name']}  [{levels}]")
    return 0


def _parse_arguments(argv: list[str] | None) -> argparse.Namespace:
    argument_parser = argparse.ArgumentParser(prog="fetch_manufacturers")
    argument_parser.add_argument("--seed", type=Path, default=DEFAULT_SEED)
    argument_parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    argument_parser.add_argument("--quiet", action="store_true")
    return argument_parser.parse_args(argv)


if __name__ == "__main__":
    raise SystemExit(main())
