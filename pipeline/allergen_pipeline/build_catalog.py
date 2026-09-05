"""שלב 1 של הבנייה: קטלוג מלא מקבצי שקיפות מחירים, בלי אלרגנים.

הפקודה מורידה קבצי PriceFull, מפרקת אותם, ממזגת מוצרים לפי ברקוד,
מסווגת למחלקות, ובונה תמונת מצב SQLite שהאפליקציה יכולה לפתוח.

הקטלוג עומד בפני עצמו ואינו תלוי בזמינות מידע אלרגנים. ראו ADR-0001.
בשלב הזה כל מוצר יוצג באפליקציה עם "אין מידע", וזה בסדר: היעדר המוצר
מהמאגר הוא כישלון חמור יותר מהיעדר מידע עליו.

    python -m allergen_pipeline.build_catalog --stores 5
"""

from __future__ import annotations

import argparse
import json
import gzip
import sys
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path

from .catalog.product import Product, RetailerOffer, build, merge_observation
from .domain.claims import AllergenClaim
from .enrich import (
    OffCache,
    collect_from_open_food_facts,
    load_manufacturer_claims,
    load_rami_levy_claims,
    load_retailer_claims,
    merge_claim_sources,
)
from .ingredients.mapping import IngredientAllergenMap
from .domain.resolution import ResolvedAllergens, resolve
from .snapshot import build as snapshot_builder
from .sources.base import RunStats, SanityCheckFailed, check_run
from .sources.price_transparency import parser, published_prices, retailers, shufersal

DEFAULT_OUTPUT = Path("data/snapshots/allergen-snapshot.sqlite")
DEFAULT_CACHE = Path("data/cache/openfoodfacts.json")
DEFAULT_MANUFACTURER_CLAIMS = Path("data/cache/manufacturer_claims.json")
DEFAULT_RETAILER_CLAIMS = Path("data/cache/shufersal_allergens.json")
DEFAULT_RAMI_LEVY_CLAIMS = Path("data/cache/rami_levy_allergens.json")


def collect_shufersal_offers(
    store_limit: int,
    page_limit: int,
    verbose: bool = True,
) -> tuple[list[RetailerOffer], int]:
    """מוריד ומפרק קבצי PriceFull. מחזיר הצעות ומספר שורות שנדחו."""
    offers: list[RetailerOffer] = []
    rejected = 0
    downloaded = 0

    with shufersal.make_client() as client:
        page = 1
        while downloaded < store_limit and page <= page_limit:
            remote_files = shufersal.list_price_full_files(client, page=page)
            if not remote_files:
                break

            for remote in remote_files:
                if downloaded >= store_limit:
                    break
                try:
                    raw = shufersal.download(client, remote)
                except Exception as error:  # noqa: BLE001 - קובץ אחד לא מפיל ריצה
                    _log(verbose, f"  דילוג על {remote.filename}: {error}")
                    continue

                parsed = parser.parse_bytes(_gunzip(raw), "shufersal")
                offers.extend(parsed.offers)
                rejected += parsed.skipped_invalid_barcode
                downloaded += 1
                _log(
                    verbose,
                    f"  {remote.filename}: {len(parsed.offers)} פריטים, "
                    f"{parsed.skipped_invalid_barcode} ברקודים נפסלו, "
                    f"{parsed.skipped_weighted} שקילים",
                )
            page += 1

    return offers, rejected


def collect_published_prices_offers(
    retailer_id: str,
    username: str,
    store_limit: int,
    verbose: bool = True,
) -> tuple[list[RetailerOffer], int]:
    """מוריד ומפרק קבצי PriceFull מהפורטל המשותף."""
    offers: list[RetailerOffer] = []
    rejected = 0

    with published_prices.make_client() as client:
        try:
            published_prices.login(client, username)
        except Exception as error:  # noqa: BLE001 - רשת אחת לא מפילה ריצה
            _log(verbose, f"  {retailer_id}: התחברות נכשלה, {error}")
            return [], 0

        remote_files = published_prices.list_price_full_files(client)
        _log(verbose, f"  {retailer_id}: {len(remote_files)} קבצי קטלוג בפורטל")

        for remote in remote_files[:store_limit]:
            try:
                raw = published_prices.download(client, remote)
            except Exception as error:  # noqa: BLE001
                _log(verbose, f"    דילוג על {remote.filename}: {error}")
                continue

            parsed = parser.parse_bytes(_gunzip(raw), retailer_id)
            offers.extend(parsed.offers)
            rejected += parsed.skipped_invalid_barcode
            _log(
                verbose,
                f"    {remote.filename}: {len(parsed.offers)} פריטים, "
                f"{parsed.skipped_invalid_barcode} ברקודים נפסלו",
            )

    return offers, rejected


def _log(verbose: bool, message: str) -> None:
    if verbose:
        print(message)


def _gunzip(raw: bytes) -> bytes:
    return gzip.decompress(raw) if raw[:2] == b"\x1f\x8b" else raw


def merge_into_products(offers: list[RetailerOffer]) -> dict[str, Product]:
    """ממזג הצעות מכל הסניפים והרשתות למוצרים קנוניים לפי ברקוד."""
    by_barcode: dict[str, list[RetailerOffer]] = defaultdict(list)
    for offer in offers:
        by_barcode[offer.barcode].append(offer)

    products: dict[str, Product] = {}
    for barcode, barcode_offers in by_barcode.items():
        product = build(barcode, barcode_offers)
        existing = products.get(barcode)
        products[barcode] = (
            merge_observation(existing, product) if existing else product
        )
    return products


def main(argv: list[str] | None = None) -> int:
    arguments = _parse_arguments(argv)
    today = date.today()

    print(f"בונה קטלוג. {arguments.stores} קבצי סניף משופרסל.")
    offers, rejected = collect_shufersal_offers(
        store_limit=arguments.stores,
        page_limit=arguments.pages,
        verbose=not arguments.quiet,
    )

    for retailer in retailers.RETAILERS:
        if not retailer.requires_login or retailer.id not in arguments.retailers:
            continue
        extra, extra_rejected = collect_published_prices_offers(
            retailer_id=retailer.id,
            username=retailer.username or "",
            store_limit=arguments.stores,
            verbose=not arguments.quiet,
        )
        offers.extend(extra)
        rejected += extra_rejected

    if not offers:
        print("לא התקבלו פריטים. הריצה נפסלת ולא נכתב דבר.", file=sys.stderr)
        return 1

    stats = RunStats(
        adapter_id="price_transparency:shufersal",
        rows=len(offers) + rejected,
        started_at=_now(),
        finished_at=_now(),
        missing_required=rejected,
    )
    try:
        check_run(stats, previous_rows=arguments.previous_rows)
    except SanityCheckFailed as failure:
        print(f"בדיקת שפיות נכשלה: {failure}", file=sys.stderr)
        print("הנתונים הקיימים נשארים כמות שהם.", file=sys.stderr)
        return 2

    products = merge_into_products(offers)
    print(f"\n{len(offers)} הצעות מרשתות, {len(products)} מוצרים ייחודיים.")

    # בלי העשרה, כל מוצר נפתר לאין מידע. זה מצב תקין ולא כישלון: הקטלוג
    # עומד בפני עצמו, והמוצר מוצג עם אין מידע במקום להיעדר מהמאגר.
    claims_by_barcode: dict[str, list[AllergenClaim]] = {}
    if arguments.allergens:
        claims_by_barcode = _enrich(products, arguments)

    # תמונות מחוברות אחרי ההעשרה, כי מטמון היצרן שנקרא שם הוא גם
    # המקור לתמונה העדיפה. ראו catalog/images.py לסדר העדיפות.
    from .catalog import images as product_images

    found = product_images.collect(
        arguments.manufacturer_claims, arguments.cache, today
    )
    products, attached = product_images.attach(products, found)
    print(
        f"\nתמונות: {len(found)} זמינות לפי ברקוד, "
        f"{attached} חוברו למוצרים בקטלוג."
    )

    resolved: dict[str, ResolvedAllergens] = {
        barcode: resolve(claims_by_barcode.get(barcode, []))
        for barcode in products
    }

    # מוצר שיש לו רשימת רכיבים אך לא נמצא בה אלרגן אינו "אין מידע".
    # ההבחנה נשמרת במסד כדי שהממשק יוכל לנסח אותה נכון.
    known_ingredients = _barcodes_with_ingredients(arguments.retailer_claims)

    output = arguments.output
    result = snapshot_builder.build(
        output, list(products.values()), resolved, known_ingredients
    )
    size_mb = output.stat().st_size / (1024 * 1024)

    print(f"תמונת מצב נכתבה: {output} ({size_mb:.1f}MB)")
    print(f"  מוצרים: {result.products}")
    print(f"  עם מידע אלרגנים: {result.with_allergen_data}")
    _report_departments(products)
    print(f"\nתאריך בנייה: {today.isoformat()}")
    return 0


def _enrich(
    products: dict[str, Product], arguments: argparse.Namespace
) -> dict[str, list[AllergenClaim]]:
    """מריץ העשרת אלרגנים מול Open Food Facts ומדפיס כיסוי בפועל."""
    print("\nמעשיר אלרגנים מ-Open Food Facts.")
    cache = OffCache(arguments.cache)
    ingredient_map = IngredientAllergenMap.load()

    barcodes = sorted(products)
    if arguments.limit:
        barcodes = barcodes[: arguments.limit]

    claims, _, stats = collect_from_open_food_facts(
        barcodes=barcodes,
        cache=cache,
        observed_on=date.today(),
        ingredient_map=ingredient_map,
        verbose=not arguments.quiet,
        cache_only=arguments.cache_only,
    )

    print(f"  נשאלו: {stats.requested}")
    print(f"  נמצאו במאגר: {stats.found} ({stats.hit_rate:.0%})")
    print(f"  עם אלרגנים: {stats.with_allergens} ({stats.allergen_rate:.0%})")
    print(f"  אלרגנים נסתרים שנמצאו ברכיבים: {stats.hidden_allergens_found}")
    if stats.failures:
        print(f"  בקשות שנכשלו: {stats.failures}")
    if stats.unmapped_tags:
        top = sorted(stats.unmapped_tags.items(), key=lambda i: i[1], reverse=True)[:6]
        print("  תגיות שלא זוהו: " + ", ".join(f"{tag}({n})" for tag, n in top))

    retailer = load_retailer_claims(arguments.retailer_claims, ingredient_map)
    relevant_retailer = {
        barcode: claim_list
        for barcode, claim_list in retailer.items()
        if barcode in products
    }
    print(
        f"\nקביעות קמעונאי: {len(retailer)} במטמון, "
        f"{len(relevant_retailer)} מהן על מוצרים שבקטלוג."
    )

    rami = load_rami_levy_claims(arguments.rami_levy_claims, ingredient_map)
    relevant_rami = {
        barcode: claim_list for barcode, claim_list in rami.items() if barcode in products
    }
    print(
        f"\nקביעות רמי לוי: {len(rami)} במטמון, "
        f"{len(relevant_rami)} מהן על מוצרים שבקטלוג."
    )

    manufacturer = load_manufacturer_claims(arguments.manufacturer_claims)
    relevant = {
        barcode: claim_list
        for barcode, claim_list in manufacturer.items()
        if barcode in products
    }
    print(
        f"\nקביעות יצרן: {len(manufacturer)} במטמון, "
        f"{len(relevant)} מהן על מוצרים שבקטלוג."
    )
    return merge_claim_sources(claims, relevant_retailer, relevant_rami, relevant)


def _barcodes_with_ingredients(retailer_claims: Path) -> set[str]:
    """הברקודים שעבורם התקבלה רשימת רכיבים מלאה מהקמעונאי."""
    if not retailer_claims.exists():
        return set()
    try:
        raw = json.loads(retailer_claims.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return set()
    return {
        barcode
        for barcode, record in raw.items()
        if record and (record.get("ingredients_text") or "").strip()
    }


def _report_departments(products: dict[str, Product]) -> None:
    counts: dict[str, int] = defaultdict(int)
    for product in products.values():
        counts[product.department_id] += 1

    from .catalog import departments

    unclassified = counts.get(departments.UNCLASSIFIED_ID, 0)
    share = unclassified / len(products) if products else 0
    print(f"  לא מסווגים: {unclassified} ({share:.0%})")

    top = sorted(counts.items(), key=lambda item: item[1], reverse=True)[:8]
    print("  מחלקות מובילות:")
    for department_id, count in top:
        label = departments.DEPARTMENTS.get(department_id)
        print(f"    {label.label_he if label else department_id}: {count}")


def _now() -> datetime:
    return datetime.now()


def _parse_arguments(argv: list[str] | None) -> argparse.Namespace:
    argument_parser = argparse.ArgumentParser(
        prog="build_catalog",
        description="בונה קטלוג מוצרים מקבצי שקיפות מחירים",
    )
    argument_parser.add_argument(
        "--stores", type=int, default=5, help="כמה קבצי סניף להוריד"
    )
    argument_parser.add_argument(
        "--pages", type=int, default=20, help="כמה עמודי פורטל לסרוק לכל היותר"
    )
    argument_parser.add_argument(
        "--output", type=Path, default=DEFAULT_OUTPUT, help="נתיב תמונת המצב"
    )
    argument_parser.add_argument(
        "--previous-rows",
        type=int,
        default=None,
        help="מספר השורות בריצה הקודמת, לבדיקת שפיות",
    )
    argument_parser.add_argument(
        "--allergens", action="store_true", help="הרץ גם העשרת אלרגנים"
    )
    argument_parser.add_argument(
        "--cache", type=Path, default=DEFAULT_CACHE, help="מטמון תשובות OFF"
    )
    argument_parser.add_argument(
        "--limit", type=int, default=None, help="הגבל כמה מוצרים להעשיר"
    )
    argument_parser.add_argument(
        "--manufacturer-claims",
        type=Path,
        default=DEFAULT_MANUFACTURER_CLAIMS,
        help="קובץ קביעות יצרן מ-fetch_manufacturers",
    )
    argument_parser.add_argument(
        "--retailer-claims",
        type=Path,
        default=DEFAULT_RETAILER_CLAIMS,
        help="קובץ קביעות קמעונאי מ-fetch_retailer_allergens",
    )
    argument_parser.add_argument(
        "--rami-levy-claims",
        type=Path,
        default=DEFAULT_RAMI_LEVY_CLAIMS,
        help="קובץ קביעות רמי לוי מ-fetch_rami_levy_allergens",
    )
    argument_parser.add_argument(
        "--retailers",
        nargs="*",
        default=[],
        metavar="RETAILER",
        help="רשתות נוספות מהפורטל המשותף, למשל rami_levy victory",
    )
    argument_parser.add_argument(
        "--cache-only",
        action="store_true",
        help="אל תפנה לרשת; השתמש רק במה שכבר במטמון",
    )
    argument_parser.add_argument("--quiet", action="store_true")
    return argument_parser.parse_args(argv)


if __name__ == "__main__":
    raise SystemExit(main())
