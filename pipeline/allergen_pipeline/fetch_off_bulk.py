"""מושך את כל המוצרים הישראליים מ-Open Food Facts בתפזורת.

עד כה ההעשרה שאלה על ברקוד אחד בכל בקשה. בקטלוג של שלושים אלף מוצרים
זה שלושים אלף בקשות, ובקצב מנומס זה עשרות שעות — ולכן זה מעולם לא רץ
במלואו, ורוב הקטלוג נשאר בלי תמונה ובלי אלרגנים.

נקודת הקצה של חיפוש מרובה תועדה כאן בעבר כשבורה, והיא עובדת שוב. עם
סינון לפי מדינה היא מחזירה את כל המוצרים הישראליים שבמאגר, מאה בכל
בקשה. שמונת אלפים מוצרים נמשכים בפחות ממאה בקשות.

המשיכה כותבת לאותו מטמון שההעשרה הרגילה קוראת ממנו, ולכן היא אינה
מחליפה אותה אלא ממלאת אותה מראש. ברקוד שכבר במטמון אינו נדרס.

    python -m allergen_pipeline.fetch_off_bulk
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import httpx

from .enrich import OffCache, _as_payload
from .sources import openfoodfacts as off

SEARCH_URL = "https://world.openfoodfacts.org/api/v2/search"
DEFAULT_CACHE = Path("data/cache/openfoodfacts.json")

PAGE_SIZE = 100
REQUEST_TIMEOUT = 90.0
#: הקצב מתון בכוונה. בקשת חיפוש כבדה בהרבה מבקשת מוצר בודד.
SECONDS_BETWEEN_PAGES = 3.0
MAX_RETRIES = 3


def fetch_page(client: httpx.Client, country: str, page: int) -> tuple[list[dict], int]:
    """עמוד אחד של תוצאות. מחזיר את המוצרים ואת סך התוצאות."""
    last: Exception | None = None
    for attempt in range(MAX_RETRIES):
        try:
            response = client.get(
                SEARCH_URL,
                params={
                    "countries_tags_en": country,
                    "fields": ",".join(off.FIELDS),
                    "page_size": PAGE_SIZE,
                    "page": page,
                },
            )
            response.raise_for_status()
            payload = response.json()
            return list(payload.get("products") or []), int(payload.get("count") or 0)
        except Exception as error:  # noqa: BLE001
            last = error
            time.sleep(5 * (attempt + 1))
    raise last if last else RuntimeError(f"page {page}")


def main(argv: list[str] | None = None) -> int:
    arguments = _parse_arguments(argv)
    cache = OffCache(arguments.cache)
    before = len(cache)

    headers = {"User-Agent": off.USER_AGENT, "Accept": "application/json"}
    added = with_image = with_allergens = 0
    # ההמשך הוא לפי עמוד ולא לפי מטמון. דילוג על ברקוד מוכר חוסך כתיבה
    # אך לא את הבקשה עצמה, והמקור חוסם על מספר בקשות ולא על תוכנן. מי
    # שממשיך ריצה שנקטעה מתחיל מהעמוד שנעצר בו.
    page = arguments.start_page
    total = None

    with httpx.Client(headers=headers, timeout=REQUEST_TIMEOUT, follow_redirects=True) as client:
        while True:
            try:
                products, count = fetch_page(client, arguments.country, page)
            except Exception as error:  # noqa: BLE001
                print(f"  עמוד {page} נכשל סופית: {error}", file=sys.stderr)
                break

            if total is None:
                total = count
                pages = (total + PAGE_SIZE - 1) // PAGE_SIZE
                print(f"{total} מוצרים במדינה {arguments.country}, {pages} עמודים.")
            if not products:
                break

            for raw in products:
                parsed = off.parse_product({"status": 1, "product": raw})
                if parsed is None or cache.known(parsed.barcode):
                    continue
                cache.remember(parsed.barcode, _as_payload(parsed))
                added += 1
                if parsed.image_url:
                    with_image += 1
                if parsed.allergen_ids or parsed.trace_ids:
                    with_allergens += 1

            if page % 5 == 0:
                cache.save()
                print(f"  עמוד {page}: נוספו {added} עד כה", flush=True)

            if arguments.pages and page - arguments.start_page + 1 >= arguments.pages:
                break
            if total is not None and page * PAGE_SIZE >= total:
                break
            page += 1
            time.sleep(SECONDS_BETWEEN_PAGES)

    cache.save()
    print(
        f"\nהמטמון גדל מ-{before} ל-{len(cache)} רשומות.\n"
        f"  חדשים: {added}\n"
        f"  מהם עם תמונה: {with_image}\n"
        f"  מהם עם אלרגנים: {with_allergens}"
    )
    return 0


def _parse_arguments(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="fetch_off_bulk")
    parser.add_argument("--cache", type=Path, default=DEFAULT_CACHE)
    parser.add_argument("--country", default="israel")
    parser.add_argument("--pages", type=int, default=None, help="הגבלת עמודים לבדיקה")
    parser.add_argument("--start-page", type=int, default=1, help="המשך ריצה שנקטעה")
    return parser.parse_args(argv)


if __name__ == "__main__":
    sys.exit(main())
