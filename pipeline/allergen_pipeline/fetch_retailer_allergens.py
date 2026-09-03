"""מוריד מידע אלרגנים מדפי המוצר של שופרסל אונליין.

זהו מקור האלרגנים העיקרי של גרסה 1, ובגלל שתי סיבות: הוא מפריד במפורש
בין "מכיל" ל"עלול להכיל", וכתובת דף המוצר בנויה מהברקוד כך שאין בעיית
מנייה. כל ברקוד בקטלוג ניתן לפנייה ישירה.

הריצה איטית בכוונה. אנחנו קוראים עובדות בטיחות מדף פומבי, ואין סיבה
להטריד את השרת מעבר לנדרש. המטמון על הדיסק אומר שכל ריצה ממשיכה
מאיפה שהקודמת עצרה.

    python -m allergen_pipeline.fetch_retailer_allergens --limit 300
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

from .sources.retailers import shufersal_online

DEFAULT_SNAPSHOT = Path("data/snapshots/allergen-snapshot.sqlite")
DEFAULT_CACHE = Path("data/cache/shufersal_allergens.json")

REQUESTS_PER_MINUTE = 60
REQUEST_TIMEOUT = 45.0
MAX_RETRIES = 2

# מעל שיעור הכשלים הזה הריצה נעצרת. עדיף לעצור מאשר לייצר אלפי בקשות
# דחויות ומספרי כיסוי חסרי משמעות.
ABORT_ABOVE_FAILURE_RATE = 0.5
MIN_ATTEMPTS_BEFORE_ABORT = 40

# זרע קבוע, כדי שמדידות חוזרות ידגמו את אותם מוצרים.
SAMPLE_SEED = 20260903


@dataclass
class FetchStats:
    requested: int = 0
    fetched: int = 0
    not_found: int = 0
    with_allergen_fields: int = 0
    with_ingredients: int = 0
    failures: int = 0


def load_barcodes(snapshot: Path, limit: int | None) -> list[str]:
    """קורא ברקודים מתמונת המצב, ומדלג על מה שאינו מזון.

    הסדר מעורבב בזרע קבוע, ולא לפי ברקוד. מיון לפי ברקוד מתחיל בתחתית
    הטווח המספרי, שם יושבים קודים ישנים ונדירים שכמעט אף אחד מהם אינו
    בקטלוג האונליין; מדגם כזה מחזיר אפס תוצאות ונראה כאילו המקור שבור.
    ערבוב נותן מדגם מייצג, והזרע הקבוע שומר על ריצות חוזרות עקביות.
    """
    connection = sqlite3.connect(snapshot)
    try:
        rows = connection.execute(
            "SELECT barcode FROM products"
            " WHERE is_active = 1 AND department_id <> 'non_food'"
        ).fetchall()
    finally:
        connection.close()

    barcodes = [row[0] for row in rows]
    random.Random(SAMPLE_SEED).shuffle(barcodes)
    return barcodes[:limit] if limit else barcodes


def load_cache(path: Path) -> dict[str, dict]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def save_cache(path: Path, entries: dict[str, dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(entries, ensure_ascii=False), encoding="utf-8")


def make_client() -> httpx.Client:
    """לקוח לא פתוח עדיין. פתיחת הסשן נעשית ב-open_session."""
    return httpx.Client(
        headers=shufersal_online.BROWSER_HEADERS,
        timeout=REQUEST_TIMEOUT,
        follow_redirects=True,
    )


def open_session(client: httpx.Client) -> None:
    """מבקר בדף הראשי כדי לקבל עוגייה. בלעדיה ה-API אינו עונה."""
    client.get(shufersal_online.HOME_URL)


def fetch_one(
    client: httpx.Client, barcode: str
) -> shufersal_online.ShufersalProduct | None:
    """מושך מוצר אחד. None פירושו שאינו בקטלוג האונליין.

    האתר מחזיר 500 ולא 404 על מוצר שאינו קיים אצלו. זו אינה שגיאה
    מבחינתנו אלא תשובה, ולכן היא אינה נספרת ככישלון.
    """
    url = shufersal_online.product_url(barcode)
    response = client.get(url)
    if response.status_code in (404, 500):
        return None
    response.raise_for_status()
    return shufersal_online.parse_product_json(response.json(), barcode)


def main(argv: list[str] | None = None) -> int:
    arguments = _parse_arguments(argv)

    if not arguments.snapshot.exists():
        print(f"אין תמונת מצב ב-{arguments.snapshot}", file=sys.stderr)
        return 1

    barcodes = load_barcodes(arguments.snapshot, arguments.limit)
    cache = load_cache(arguments.cache)
    missing = [barcode for barcode in barcodes if barcode not in cache]

    print(f"{len(barcodes)} ברקודים, {len(cache)} במטמון, {len(missing)} להורדה.")
    if not missing:
        _report(cache, barcodes)
        return 0

    stats = FetchStats(requested=len(missing))
    interval = 60.0 / REQUESTS_PER_MINUTE
    started = time.monotonic()

    with make_client() as client:
        open_session(client)
        for index, barcode in enumerate(missing, start=1):
            product = None
            error: Exception | None = None
            for attempt in range(MAX_RETRIES):
                try:
                    product = fetch_one(client, barcode)
                    error = None
                    break
                except Exception as caught:  # noqa: BLE001
                    error = caught
                    time.sleep(2.0 * (attempt + 1))

            if error is not None:
                # כישלון לעולם אינו נשמר כמוצר בלי אלרגנים. ראו ADR-0002.
                stats.failures += 1
            elif product is None:
                stats.not_found += 1
                cache[barcode] = {}
            else:
                stats.fetched += 1
                if product.has_allergen_fields:
                    stats.with_allergen_fields += 1
                if product.ingredients_text:
                    stats.with_ingredients += 1
                cache[barcode] = {
                    "barcode": product.barcode,
                    "page_url": product.page_url,
                    "name": product.name,
                    "brand": product.brand,
                    "is_food": product.is_food,
                    "ingredients_text": product.ingredients_text,
                    "contains_terms": list(product.contains_terms),
                    "may_contain_terms": list(product.may_contain_terms),
                }

            if index % 50 == 0:
                save_cache(arguments.cache, cache)
                elapsed = (time.monotonic() - started) / 60
                rate = index / elapsed if elapsed else 0
                print(
                    f"  {index}/{len(missing)} ({rate:.0f} לדקה, "
                    f"{stats.with_allergen_fields} עם אלרגנים, "
                    f"{stats.failures} כשלים)",
                    flush=True,
                )

            if _should_abort(index, stats.failures):
                print("  שיעור כשלים גבוה. עוצר ושומר.", flush=True)
                break

            time.sleep(interval)

    save_cache(arguments.cache, cache)
    print(f"\n  הורדו: {stats.fetched}")
    print(f"  לא נמצאו באתר: {stats.not_found}")
    print(f"  עם שדות אלרגנים: {stats.with_allergen_fields}")
    print(f"  עם רשימת רכיבים: {stats.with_ingredients}")
    print(f"  כשלים: {stats.failures}")
    _report(cache, barcodes)
    return 0


def _should_abort(attempts: int, failures: int) -> bool:
    if attempts < MIN_ATTEMPTS_BEFORE_ABORT:
        return False
    return failures / attempts > ABORT_ABOVE_FAILURE_RATE


def _report(cache: dict[str, dict], barcodes: list[str]) -> None:
    known = [cache[b] for b in barcodes if cache.get(b)]
    with_fields = [
        entry
        for entry in known
        if entry.get("contains_terms") or entry.get("may_contain_terms")
    ]
    print(f"\nבמטמון כרגע: {len(known)} מוצרים, {len(with_fields)} עם שדות אלרגנים.")
    for entry in with_fields[:5]:
        print(
            f"  {entry['barcode']}  {entry.get('name')}  "
            f"מכיל={entry.get('contains_terms')}  "
            f"עלול={entry.get('may_contain_terms')}"
        )


def _parse_arguments(argv: list[str] | None) -> argparse.Namespace:
    argument_parser = argparse.ArgumentParser(prog="fetch_retailer_allergens")
    argument_parser.add_argument("--snapshot", type=Path, default=DEFAULT_SNAPSHOT)
    argument_parser.add_argument("--cache", type=Path, default=DEFAULT_CACHE)
    argument_parser.add_argument("--limit", type=int, default=None)
    return argument_parser.parse_args(argv)


if __name__ == "__main__":
    raise SystemExit(main())
