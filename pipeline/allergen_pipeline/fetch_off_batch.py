"""מושך מ-Open Food Facts בקבוצות ברקודים, ולא אחד אחד.

שלוש דרכים נבדקו כאן, וזו השלישית שעובדת בקנה מידה.

בקשה לכל ברקוד יציבה אך איטית: שלושים אלף מוצרים בקצב מנומס הם עשרות
שעות, ולכן ההעשרה מעולם לא רצה במלואה ורוב הקטלוג נשאר בלי תמונה.

חיפוש לפי מדינה מחזיר מאה מוצרים בבקשה, אבל נעצר קשה אחרי אלף תוצאות:
מעבר לכך המקור מחזיר 401 ואז 503, גם אחרי חצי שעה של המתנה. זו מגבלת
עומק דפדוף לא-מאומת ולא חסימה זמנית, ולכן אין טעם להמתין לה.

סינון לפי רשימת ברקודים נמצא תמיד בעמוד הראשון, ולכן מגבלת העומק אינה
חלה עליו. הוא מחזיר 503 לסירוגין, וזה נראה כמו השלת עומס ולא כדחייה
שיטתית: אותה בקשה עצמה מצליחה בניסיון הבא. לכן הניסיונות החוזרים כאן
הם עיקר העניין ולא קישוט.

    python -m allergen_pipeline.fetch_off_batch --limit 5000
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
import time
from pathlib import Path

import httpx

from .enrich import OffCache, _as_payload
from .sources import openfoodfacts as off

DEFAULT_SNAPSHOT = Path("data/snapshots/allergen-snapshot.sqlite")
DEFAULT_CACHE = Path("data/cache/openfoodfacts.json")

#: נמדד: 25 עובר, 50 נדחה כמעט תמיד. הבקשה גדלה גם באורך הכתובת וגם
#: בעבודה שהמקור עושה, ושניהם מושכים לכיוון קבוצה קטנה.
BATCH_SIZE = 25
SECONDS_BETWEEN_BATCHES = 5.0
RETRY_BACKOFF = (10, 30, 60, 120)
REQUEST_TIMEOUT = 60.0

#: מעל שיעור הכשלים הזה הריצה נעצרת, כדי לא לייצר אלפי בקשות דחויות.
ABORT_ABOVE_FAILURE_RATE = 0.6
MIN_BATCHES_BEFORE_ABORT = 12


def load_missing(snapshot: Path, cache: OffCache, limit: int | None) -> list[str]:
    """ברקודים שבקטלוג וטרם נשאלו. מוצרים שאינם מזון אינם רלוונטיים."""
    connection = sqlite3.connect(snapshot)
    try:
        rows = connection.execute(
            "SELECT barcode FROM products"
            " WHERE is_active = 1 AND department_id <> 'non_food'"
        ).fetchall()
    finally:
        connection.close()

    missing = [row[0] for row in rows if not cache.known(row[0])]
    return missing[:limit] if limit else missing


def fetch_group(client: httpx.Client, barcodes: list[str]) -> list[off.OffProduct] | None:
    """קבוצה אחת. מחזיר None כשכל הניסיונות נכשלו.

    None אינו "לא נמצא". ברקוד שלא הוחזר בתשובה מוצלחת אינו במאגר,
    וזו עובדה שנרשמת; קבוצה שנכשלה אינה נרשמת כלל, כי כישלון רשת
    שנשמר כ"אין אלרגנים" הוא בדיוק הטעות המסוכנת. ראו ADR-0002.
    """
    for attempt, wait in enumerate((0, *RETRY_BACKOFF)):
        if wait:
            time.sleep(wait)
        try:
            response = client.get(
                off.API_SEARCH_URL,
                params={
                    "code": ",".join(barcodes),
                    "fields": ",".join(off.FIELDS),
                    "page_size": len(barcodes),
                },
            )
            response.raise_for_status()
            return off.parse_search_payload(response.json())
        except Exception:  # noqa: BLE001
            continue
    return None


def main(argv: list[str] | None = None) -> int:
    arguments = _parse_arguments(argv)
    cache = OffCache(arguments.cache)
    before = len(cache)

    pending = load_missing(arguments.snapshot, cache, arguments.limit)
    if not pending:
        print("אין ברקודים למשיכה.")
        return 0

    groups = [
        pending[index : index + BATCH_SIZE]
        for index in range(0, len(pending), BATCH_SIZE)
    ]
    print(f"{len(pending)} ברקודים, {len(groups)} קבוצות של {BATCH_SIZE}.")

    headers = {"User-Agent": off.USER_AGENT, "Accept": "application/json"}
    found = not_found = failed = with_image = with_allergens = 0

    with httpx.Client(headers=headers, timeout=REQUEST_TIMEOUT, follow_redirects=True) as client:
        for index, group in enumerate(groups, 1):
            products = fetch_group(client, group)
            if products is None:
                failed += 1
                if index >= MIN_BATCHES_BEFORE_ABORT and failed / index > ABORT_ABOVE_FAILURE_RATE:
                    print("  שיעור כשלים גבוה. המקור אינו זמין; עוצר ושומר.", flush=True)
                    break
                time.sleep(SECONDS_BETWEEN_BATCHES)
                continue

            returned = {product.barcode for product in products}
            for product in products:
                cache.remember(product.barcode, _as_payload(product))
                found += 1
                if product.image_url:
                    with_image += 1
                if product.allergen_ids or product.trace_ids:
                    with_allergens += 1
            for barcode in group:
                if barcode not in returned:
                    cache.remember(barcode, None)
                    not_found += 1

            if index % 20 == 0:
                cache.save()
                print(
                    f"  {index}/{len(groups)} קבוצות, נמצאו {found}, "
                    f"תמונות {with_image}, כשלים {failed}",
                    flush=True,
                )
            time.sleep(SECONDS_BETWEEN_BATCHES)

    cache.save()
    print(
        f"\nהמטמון גדל מ-{before} ל-{len(cache)}.\n"
        f"  נמצאו במאגר: {found}\n"
        f"  אינם במאגר: {not_found}\n"
        f"  מהם עם תמונה: {with_image}\n"
        f"  מהם עם אלרגנים: {with_allergens}\n"
        f"  קבוצות שנכשלו: {failed}"
    )
    return 0


def _parse_arguments(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="fetch_off_batch")
    parser.add_argument("--snapshot", type=Path, default=DEFAULT_SNAPSHOT)
    parser.add_argument("--cache", type=Path, default=DEFAULT_CACHE)
    parser.add_argument("--limit", type=int, default=None)
    return parser.parse_args(argv)


if __name__ == "__main__":
    sys.exit(main())
