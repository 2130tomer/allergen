"""מתאם שופרסל אונליין: מכיל ועלול להכיל, מופרדים במפורש.

זהו מקור האלרגנים הטוב ביותר שנמצא, ומסיבה מפתיעה — הוא טוב יותר
מאתר היצרן עצמו. אסם מפרסמת רשימה שטוחה שמאחדת "מכיל" ו"עלול להכיל"
לשורה אחת, בעוד ששופרסל מפרסמת שני שדות נפרדים ומקודדים.

הנתונים מגיעים מ-JSON מובנה ולא מגירוד HTML. לכל מוצר יש רשימת
classifications, וכל אחת נושאת קוד שממנו נגזרת המשמעות:

    125  מכיל
    126  עלול להכיל
    110  רשימת רכיבים

שם השדה של 125 ושל 126 זהה — שניהם "אלרגנים" — ולכן **הקוד הוא מה
שמבחין ביניהם, לא השם**. היפוך בין השניים היה הופך "עלול להכיל"
ל"מכיל" ולהפך, ולכן המיפוי אומת מול תווית ה-HTML של שני מוצרים לפני
שנכנס לשימוש.

שדה sku מחזיק את הברקוד, ולכן אין בעיית מנייה: אפשר לפנות ישירות לפי
ברקוד מהקטלוג. מוצר שאינו בקטלוג האונליין מחזיר 500.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from ...catalog import barcode as barcode_utils

HOME_URL = "https://www.shufersal.co.il/online/he/A"
PRODUCT_JSON_URL = "https://www.shufersal.co.il/online/he/products/P_{barcode}"

# כותרות של דפדפן אמיתי. בקשה דלה נחסמת.
BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "he-IL,he;q=0.9,en-US;q=0.8",
}

GROUP_CONTAINS = "125"
GROUP_MAY_CONTAIN = "126"
GROUP_INGREDIENTS = "110"

_SEPARATORS = re.compile(r"[,;/|\n\r\t]+")


@dataclass(frozen=True)
class ShufersalProduct:
    """מוצר כפי שנקרא מ-API של שופרסל אונליין."""

    barcode: str
    page_url: str
    name: str | None = None
    brand: str | None = None
    is_food: bool = True
    ingredients_text: str | None = None
    contains_terms: tuple[str, ...] = ()
    may_contain_terms: tuple[str, ...] = ()

    @property
    def has_allergen_fields(self) -> bool:
        return bool(self.contains_terms or self.may_contain_terms)


def _group_of(feature_code: str) -> str:
    """מספר קבוצת הסיווג, כמו 125 מתוך .../125.125_125."""
    return feature_code.rsplit("/", 1)[-1].split(".", 1)[0]


def _values_by_group(payload: dict) -> dict[str, list[str]]:
    grouped: dict[str, list[str]] = {}
    for classification in payload.get("classifications") or []:
        for feature in classification.get("features") or []:
            group = _group_of(feature.get("code") or "")
            values = [
                str(entry.get("value")).strip()
                for entry in feature.get("featureValues") or []
                if entry.get("value")
            ]
            if values:
                grouped.setdefault(group, []).extend(values)
    return grouped


def split_terms(values: list[str]) -> tuple[str, ...]:
    """מפרק ערכי אלרגן למונחים בודדים.

    שומר גם את הביטוי המלא, כי "גלוטן חיטה" צריך להתאים כביטוי אחד
    ולא רק כשתי מילים נפרדות.
    """
    terms: list[str] = []
    for value in values:
        for chunk in _SEPARATORS.split(value):
            chunk = chunk.strip()
            if not chunk:
                continue
            terms.append(chunk)
            terms.extend(word for word in chunk.split() if word != chunk)
    return tuple(dict.fromkeys(terms))


def parse_product_json(payload: dict, requested_barcode: str) -> ShufersalProduct | None:
    """הופך תשובת API אחת למוצר.

    הברקוד נלקח משדה sku של התשובה ולא מהבקשה, ואם הם אינם תואמים
    המוצר נפסל. שיוך אלרגנים לברקוד הלא נכון הוא בדיוק סוג הטעות
    שהאפליקציה אמורה למנוע.
    """
    sku = barcode_utils.normalize(str(payload.get("sku") or ""))
    requested = barcode_utils.normalize(requested_barcode)
    if not sku or barcode_utils.to_gtin13(sku) != barcode_utils.to_gtin13(requested):
        return None

    grouped = _values_by_group(payload)
    ingredients = " ".join(grouped.get(GROUP_INGREDIENTS, [])).strip()

    return ShufersalProduct(
        barcode=barcode_utils.to_gtin13(sku),
        page_url=PRODUCT_JSON_URL.format(barcode=requested),
        name=payload.get("name") or None,
        brand=payload.get("brandName") or None,
        is_food=bool(payload.get("food", True)),
        ingredients_text=ingredients or None,
        contains_terms=split_terms(grouped.get(GROUP_CONTAINS, [])),
        may_contain_terms=split_terms(grouped.get(GROUP_MAY_CONTAIN, [])),
    )


def product_url(barcode: str) -> str:
    return PRODUCT_JSON_URL.format(barcode=barcode)
