"""חיבור תמונת מוצר לקטלוג, לפי ברקוד.

סדר העדיפות בין המקורות הוא החלטת מוצר ולא נוחות טכנית. ראו ADR-0005.

תמונת היצרן קודמת לכל. היא מצולמת מהאריזה שהיצרן עצמו משווק, ולכן
היא זו שתואמת את מה שהמשתמש יראה על המדף.

Open Food Facts הוא המקור המשני. הוא אינו רשת שיווק אלא מאגר פתוח
בעל רישיון חופשי, ולכן מותר להציג ממנו תמונה עם ייחוס.

תמונות מאתרי רשתות השיווק אינן נאספות כאן כלל, גם כשהן זמינות
ונוחות יותר. זו הגבלה מכוונת.

השיוך הוא לפי ברקוד ולפי ברקוד בלבד. תמונה שאין לה ברקוד ודאי אינה
נכנסת: תמונה שגויה על מוצר אינה בעיה קוסמטית אלא הצגה של מוצר אחר.
"""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import date
from pathlib import Path

from .product import Product, ProductImage

MANUFACTURER_SOURCE = "אתר היצרן"
OFF_SOURCE = "Open Food Facts"


def _load(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def collect(
    manufacturer_claims: Path,
    off_cache: Path,
    fetched_on: date | None = None,
) -> dict[str, ProductImage]:
    """אוסף כתובות תמונה לפי ברקוד, מהמקור העדיף כלפי מטה."""
    when = fetched_on or date.today()
    images: dict[str, ProductImage] = {}

    # המשני נטען ראשון כדי שהעדיף ידרוס אותו.
    for barcode, record in _load(off_cache).items():
        url = (record or {}).get("image_front_url")
        if url:
            images[barcode] = ProductImage(
                url=url, source_name=OFF_SOURCE, fetched_on=when
            )

    for barcode, record in _load(manufacturer_claims).items():
        url = (record or {}).get("image_url")
        if url:
            images[barcode] = ProductImage(
                url=url, source_name=MANUFACTURER_SOURCE, fetched_on=when
            )

    return images


def attach(
    products: dict[str, Product], images: dict[str, ProductImage]
) -> tuple[dict[str, Product], int]:
    """מחבר תמונות למוצרים ומחזיר כמה חוברו בפועל.

    תמונה שכבר קיימת על המוצר אינה נדרסת, כדי שריצה חוזרת לא תחליף
    תמונת יצרן שנשמרה קודם בתמונה ממקור חלש יותר.
    """
    attached = 0
    updated = dict(products)
    for barcode, image in images.items():
        product = updated.get(barcode)
        if product is None or product.image is not None:
            continue
        updated[barcode] = replace(product, image=image)
        attached += 1
    return updated, attached
