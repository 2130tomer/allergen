"""מוריד מידע אלרגנים מרמי לוי אונליין.

הקמעונאי השני, אחרי ששופרסל מוצתה. ברירת המחדל כאן שונה משופרסל
בכוונה: נמשכים קודם המוצרים שאין עליהם מידע כלל, כי הם הסיבה שהמתאם
נבנה. אין טעם לשאול שוב על מוצר שכבר יש עליו קביעה מקמעונאי אחר.

    python -m allergen_pipeline.fetch_rami_levy_allergens --limit 300

הריצה איטית בכוונה, כמו אצל שופרסל: אנחנו קוראים עובדות בטיחות מדף
פומבי ואין סיבה להטריד את השרת. המטמון על הדיסק אומר שכל ריצה ממשיכה
מאיפה שהקודמת עצרה.
"""

from __future__ import annotations

import argparse
import json
import random
import sqlite3
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import httpx

from .cache import is_fresh, observed_record, write_json
from .sources.retailers import rami_levy_online as rami

DEFAULT_SNAPSHOT = Path("data/snapshots/allergen-snapshot.sqlite")
DEFAULT_CACHE = Path("data/cache/rami_levy_allergens.json")

REQUESTS_PER_MINUTE = 30
REQUEST_TIMEOUT = 30.0
MAX_RETRIES = 2

ABORT_ABOVE_FAILURE_RATE = 0.5
MIN_ATTEMPTS_BEFORE_ABORT = 40

SAMPLE_SEED = 20260905


@dataclass
class FetchStats:
    requested: int = 0
    fetched: int = 0
    not_found: int = 0
    with_allergen_fields: int = 0
    with_ingredients: int = 0
    unknown_codes: int = 0
    failures: int = 0


def load_barcodes(snapshot: Path, limit: int | None, only_missing: bool) -> list[str]:
    """ברקודים למשיכה, מעורבבים בזרע קבוע.

    הערבוב אינו קישוט. מיון לפי ברקוד מתחיל בתחתית הטווח, שם יושבים
    קודים ישנים שכמעט אינם בקטלוג האונליין, ומדגם כזה מחזיר אפס ונראה
    כאילו המקור שבור.
    """
    where = "is_active = 1 AND department_id <> 'non_food'"
    if only_missing:
        where += " AND has_allergen_data = 0"
    connection = sqlite3.connect(snapshot)
    try:
        rows = connection.execute(f"SELECT barcode FROM products WHERE {where}").fetchall()
    finally:
        connection.close()

    barcodes = [row[0] for row in rows]
    random.Random(SAMPLE_SEED).shuffle(barcodes)
    return barcodes[:limit] if limit else barcodes


def _load_cache(path: Path) -> dict[str, dict]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _save_cache(path: Path, entries: dict[str, dict]) -> None:
    write_json(path, entries)


def _fetch_one(client: httpx.Client, barcode: str) -> rami.RamiLevyProduct | None:
    """כישלון רשת מורם החוצה ואינו נרשם כמוצר בלי אלרגנים. ראו ADR-0002."""
    last: Exception | None = None
    for attempt in range(MAX_RETRIES):
        try:
            response = client.post(rami.API_URL, json=rami.request_body(barcode))
            response.raise_for_status()
            return rami.parse_product(response.json(), barcode)
        except Exception as error:  # noqa: BLE001
            last = error
            time.sleep(2 * (attempt + 1))
    raise last if last else RuntimeError(barcode)


def main(argv: list[str] | None = None) -> int:
    arguments = _parse_arguments(argv)
    barcodes = load_barcodes(arguments.snapshot, None, not arguments.all)
    cache = _load_cache(arguments.cache)
    pending = [b for b in barcodes if arguments.refresh or not is_fresh(cache.get(b))]
    if arguments.limit is not None:
        pending = pending[:arguments.limit]

    stats = FetchStats(requested=len(pending))
    print(f"{len(barcodes)} מועמדים, {len(pending)} טרם נמשכו.")
    if not pending:
        print("אין מה למשוך.")
        return 0

    delay = 60.0 / arguments.requests_per_minute
    headers = {
        "User-Agent": "allergen-il/0.1 (allergen catalog for Israel)",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    completed = 0
    with httpx.Client(headers=headers, timeout=REQUEST_TIMEOUT, follow_redirects=True) as client:
        for barcode in pending:
            completed += 1
            try:
                product = _fetch_one(client, barcode)
            except Exception:  # noqa: BLE001
                stats.failures += 1
                if _should_abort(completed, stats.failures):
                    print("  שיעור כשלים גבוה. המקור חוסם; עוצר ושומר.", flush=True)
                    break
                time.sleep(delay)
                continue

            if product is None:
                stats.not_found += 1
                cache[barcode] = observed_record(None, cache.get(barcode))
            else:
                stats.fetched += 1
                if product.has_allergen_fields:
                    stats.with_allergen_fields += 1
                if product.ingredients_text:
                    stats.with_ingredients += 1
                stats.unknown_codes += len(product.unknown_codes)
                cache[barcode] = observed_record({
                    "barcode": product.barcode,
                    "name": product.name,
                    "brand": product.brand,
                    "contains": list(product.contains_ids),
                    "may_contain": list(product.may_contain_ids),
                    "ingredients_text": product.ingredients_text,
                    "unknown_codes": list(product.unknown_codes),
                    "page_url": product.page_url,
                }, cache.get(barcode))

            if completed % 50 == 0:
                _save_cache(arguments.cache, cache)
                print(
                    f"  {completed}/{len(pending)} "
                    f"(נמצאו {stats.fetched}, עם אלרגנים {stats.with_allergen_fields}, "
                    f"כשלים {stats.failures})",
                    flush=True,
                )
            time.sleep(delay)

    _save_cache(arguments.cache, cache)
    print(
        f"\nנמשכו {completed}. נמצאו {stats.fetched}, לא נמצאו {stats.not_found}, "
        f"כשלים {stats.failures}."
    )
    print(
        f"  עם שדות אלרגנים: {stats.with_allergen_fields}\n"
        f"  עם רשימת רכיבים: {stats.with_ingredients}\n"
        f"  קודים לא מזוהים: {stats.unknown_codes}"
    )
    return 1 if stats.failures else 0


def _should_abort(completed: int, failures: int) -> bool:
    if completed < MIN_ATTEMPTS_BEFORE_ABORT:
        return False
    return failures / completed > ABORT_ABOVE_FAILURE_RATE


def _parse_arguments(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="fetch_rami_levy_allergens")
    parser.add_argument("--snapshot", type=Path, default=DEFAULT_SNAPSHOT)
    parser.add_argument("--cache", type=Path, default=DEFAULT_CACHE)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument(
        "--all",
        action="store_true",
        help="לא רק מוצרים חסרי מידע, אלא כל הקטלוג.",
    )
    parser.add_argument("--refresh", action="store_true", help="Refresh cached observations")
    parser.add_argument("--requests-per-minute", type=int, default=REQUESTS_PER_MINUTE)
    args = parser.parse_args(argv)
    if args.limit is not None and args.limit < 1:
        parser.error("--limit must be positive")
    if args.requests_per_minute < 1:
        parser.error("--requests-per-minute must be positive")
    return args


if __name__ == "__main__":
    sys.exit(main())
