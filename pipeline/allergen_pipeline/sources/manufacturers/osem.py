"""מתאם אתר אסם-נסטלה.

שני ממצאים מהאתר שקובעים את המימוש:

1. כתובת תמונת המוצר מכילה את הברקוד בשם הקובץ, בתבנית
   product_images_new/{מזהה}_{ברקוד}[_{מספר}]_Enlarge.jpg. זהו הקישור
   הוודאי היחיד בין דף המוצר לברקוד, שכן כתובת הדף מבוססת שם עברי.

2. טאב האלרגנים מכיל רשימה שטוחה. בדף במבה קלאסית כתוב שם "בוטנים
   סויה" בלי הבחנה, למרות שהמוצר מכיל בוטנים ורק עלול להכיל סויה.

הדף מוגן מפני בקשות HTTP פשוטות ומחזיר 403, ותוכן הטאבים נטען רק
בלחיצה. לכן הגירוד עצמו מתבצע בדפדפן אוטומטי, והמודול הזה מקבל את
ה-HTML אחרי שהטאבים כבר הורחבו.
"""

from __future__ import annotations

import re
from html.parser import HTMLParser

from ...catalog import barcode as barcode_utils
from .base import ManufacturerProduct

MANUFACTURER_ID = "osem"
MANUFACTURER_NAME = "אסם-נסטלה"
BASE_URL = "https://www.osem-nestle.co.il"

# הכותרות של האקורדיון בדף המוצר.
ALLERGENS_PANEL_TITLE = "אלרגנים"
INGREDIENTS_PANEL_TITLE = "רשימת מרכיבים"
_PANEL_TITLES = (ALLERGENS_PANEL_TITLE, INGREDIENTS_PANEL_TITLE)

_IMAGE_BARCODE = re.compile(
    r"product_images[^\"'\s]*?/\d+_(\d{8,14})(?:_\d+)?_[A-Za-z]+\.(?:jpg|jpeg|png|webp)",
    re.IGNORECASE,
)
_IMAGE_URL = re.compile(
    r"(?:https?:)?//[^\"'\s]*product_images[^\"'\s]*?\.(?:jpg|jpeg|png|webp)[^\"'\s]*",
    re.IGNORECASE,
)
_SEPARATORS = re.compile(r"[,،;/|\n\r\t]+")


class _PanelParser(HTMLParser):
    """אוסף את תוכן הפאנלים לפי כותרת, ואת שם המוצר מהכותרת הראשית."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.panels: dict[str, list[str]] = {}
        self.title: str | None = None
        self._current_title: str | None = None
        self._capture_title = False
        self._capture_h1 = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        classes = (attributes.get("class") or "").split()
        if tag in ("h2", "h3") and "panel-title" in classes:
            # כותרת פאנל חדשה סוגרת את הקודמת, גם כשהיא לא מעניינת אותנו.
            self._capture_title = True
            self._current_title = None
        elif tag == "h1":
            self._capture_h1 = True

    def handle_endtag(self, tag: str) -> None:
        if tag in ("h2", "h3") and self._capture_title:
            self._capture_title = False
        elif tag == "h1":
            self._capture_h1 = False

    def handle_data(self, data: str) -> None:
        text = data.strip()
        if not text:
            return
        if self._capture_h1 and not self.title:
            self.title = text
            return
        if self._capture_title:
            if text in _PANEL_TITLES:
                self._current_title = text
                self.panels.setdefault(text, [])
            else:
                self._current_title = None
            return
        if self._current_title and text not in _PANEL_TITLES:
            self.panels[self._current_title].append(text)


def extract_barcode(html: str) -> str | None:
    """הברקוד מתוך כתובת תמונת המוצר.

    מחזיר None כשאין התאמה ודאית. הקישור לא נעשה לפי שם המוצר, כי
    התאמת שמות היא מקור לשגיאות שיוך.
    """
    for match in _IMAGE_BARCODE.finditer(html):
        candidate = match.group(1)
        if barcode_utils.is_usable(candidate):
            return barcode_utils.to_gtin13(candidate)
    return None


def extract_image_url(html: str, barcode: str | None) -> str | None:
    """כתובת התמונה שברקודה תואם למוצר."""
    for match in _IMAGE_URL.finditer(html):
        url = match.group(0)
        if barcode and barcode[-8:] not in barcode_utils.normalize(url):
            continue
        if url.startswith("//"):
            return f"https:{url}"
        return url
    return None


def split_allergen_terms(panel_text: str) -> tuple[str, ...]:
    """מפרק את תוכן טאב האלרגנים למונחים בודדים.

    האתר מפריד לפעמים בפסיק ולפעמים ברווח בלבד, ולכן כל מילה נחשבת
    למונח בפני עצמו ומועברת למיפוי כדי שיחליט אם היא אלרגן.
    """
    if not panel_text:
        return ()
    parts: list[str] = []
    for chunk in _SEPARATORS.split(panel_text):
        chunk = chunk.strip()
        if not chunk:
            continue
        parts.append(chunk)
        parts.extend(word for word in chunk.split() if word != chunk)
    return tuple(dict.fromkeys(parts))


def parse_product_page(html: str, page_url: str) -> ManufacturerProduct:
    """קורא דף מוצר של אסם אחרי שהאקורדיון הורחב."""
    parser = _PanelParser()
    parser.feed(html)

    allergen_text = " ".join(parser.panels.get(ALLERGENS_PANEL_TITLE, []))
    ingredients_text = " ".join(parser.panels.get(INGREDIENTS_PANEL_TITLE, []))
    barcode = extract_barcode(html)

    return ManufacturerProduct(
        manufacturer_id=MANUFACTURER_ID,
        manufacturer_name=MANUFACTURER_NAME,
        page_url=page_url,
        product_name=parser.title,
        barcode=barcode,
        image_url=extract_image_url(html, barcode),
        ingredients_text=ingredients_text or None,
        raw_allergen_terms=split_allergen_terms(allergen_text),
    )
