"""לקוח HTTP לאתר אסם-נסטלה.

התברר שאין צורך בדפדפן אוטומטי. הבקשה נכשלה ב-403 רק בגלל כותרות
דלות; עם כותרות של דפדפן אמיתי דף המוצר חוזר 200, ותוכן האקורדיון
כולו נמצא כבר ב-HTML הסטטי ואינו נטען בלחיצה.

מה שכן חסום: דפי המותג, sitemap.xml ו-robots.txt מחזירים 403. לכן
אפשר לקרוא דף מוצר שכתובתו ידועה, אך לא לסרוק את הקטלוג. מניית
המוצרים דורשת דפדפן ונדחתה לגרסה הבאה; ראו README.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path

import httpx

from .base import ManufacturerProduct
from .osem import parse_product_page

# כותרות של דפדפן אמיתי. בלעדיהן ההגנה של האתר מחזירה 403.
BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,"
        "image/avif,image/webp,*/*;q=0.8"
    ),
    "Accept-Language": "he-IL,he;q=0.9,en-US;q=0.8",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
}

# גירוד איטי ומנומס. אנחנו לוקחים עובדות בטיחות שהיצרן פרסם בעצמו.
PAUSE_BETWEEN_PAGES_SECONDS = 1.5
REQUEST_TIMEOUT = 45.0


@dataclass
class CrawlStats:
    requested: int = 0
    fetched: int = 0
    linkable: int = 0
    with_allergens: int = 0
    failures: int = 0


def make_client() -> httpx.Client:
    return httpx.Client(
        headers=BROWSER_HEADERS, timeout=REQUEST_TIMEOUT, follow_redirects=True
    )


def fetch_product(client: httpx.Client, url: str) -> ManufacturerProduct | None:
    """מוריד דף מוצר אחד ומפרק אותו."""
    response = client.get(url)
    if response.status_code != 200:
        return None
    return parse_product_page(response.text, url)


def load_seed_urls(path: Path) -> list[str]:
    """קורא רשימת כתובות מוצר, שורה לשורה.

    זהו הפתרון לגרסה 1 במקום סריקה: רשימה מתוחזקת ידנית של דפי מוצר.
    היא מוגבלת, אבל היא אמיתית ואינה מתחזה לכיסוי מלא.
    """
    if not path.exists():
        return []
    return [
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    ]


def crawl(
    urls: list[str], verbose: bool = True
) -> tuple[list[ManufacturerProduct], CrawlStats]:
    """מוריד ומפרק רשימת דפי מוצר, לאט."""
    stats = CrawlStats(requested=len(urls))
    products: list[ManufacturerProduct] = []

    with make_client() as client:
        for index, url in enumerate(urls, start=1):
            try:
                product = fetch_product(client, url)
            except Exception as error:  # noqa: BLE001 - דף אחד לא מפיל ריצה
                stats.failures += 1
                if verbose:
                    print(f"  נכשל {url}: {error}")
                continue

            if product is None:
                stats.failures += 1
                continue

            stats.fetched += 1
            if product.is_linkable:
                stats.linkable += 1
                products.append(product)
                if product.raw_allergen_terms:
                    stats.with_allergens += 1
            elif verbose:
                # בלי ברקוד ודאי אין שיוך אלרגנים בכלל. כלל הברזל.
                print(f"  ללא ברקוד, מדולג: {product.product_name or url}")

            if verbose and index % 10 == 0:
                print(f"  {index}/{len(urls)}", flush=True)
            time.sleep(PAUSE_BETWEEN_PAGES_SECONDS)

    return products, stats
