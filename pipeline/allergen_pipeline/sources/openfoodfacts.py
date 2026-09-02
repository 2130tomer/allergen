"""מתאם Open Food Facts.

המקור היחיד מבין השלושה ששומר את ההבחנה בין מכיל לעלול להכיל בשני
שדות נפרדים: allergens_tags מול traces_tags. בגלל זה הוא גובר על אתר
היצרן בשאלת הרמה, למרות דרגת אמינות נמוכה יותר. ראו ADR-0004.

התגיות מגיעות מעורבות עברית ואנגלית, למשל en:בוטנים לצד en:soybeans,
ולכן הפענוח מתבסס על מילון דו-לשוני ולא על השפה של התגית.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from ..domain import allergens
from ..domain.claims import AllergenClaim, Level, Source
from ..text import hebrew

API_PRODUCT_URL = "https://world.openfoodfacts.org/api/v2/product/{barcode}.json"

FIELDS = (
    "code",
    "product_name",
    "product_name_he",
    "brands",
    "allergens_tags",
    "traces_tags",
    "ingredients_text",
    "ingredients_text_he",
    "image_front_url",
    "countries_tags",
)

# מהתגית של Open Food Facts אל הרשימה הסגורה שלנו, בשתי השפות.
_TAG_TO_ALLERGEN: dict[str, str] = {
    "gluten": "gluten",
    "wheat": "gluten",
    "גלוטן": "gluten",
    "חיטה": "gluten",
    "milk": "milk",
    "חלב": "milk",
    "eggs": "eggs",
    "egg": "eggs",
    "ביצים": "eggs",
    "peanuts": "peanuts",
    "peanut": "peanuts",
    "בוטנים": "peanuts",
    "soybeans": "soy",
    "soy": "soy",
    "סויה": "soy",
    "sesame-seeds": "sesame",
    "sesame": "sesame",
    "שומשום": "sesame",
    "fish": "fish",
    "דגים": "fish",
    "crustaceans": "crustaceans",
    "סרטנים": "crustaceans",
    "molluscs": "molluscs",
    "רכיכות": "molluscs",
    "nuts": allergens.TREE_NUTS_ID,
    "tree-nuts": allergens.TREE_NUTS_ID,
    "אגוזים": allergens.TREE_NUTS_ID,
    "almonds": "almond",
    "שקדים": "almond",
    "walnuts": "walnut",
    "cashew": "cashew",
    "cashew-nuts": "cashew",
    "pecan-nuts": "pecan",
    "pistachio": "pistachio",
    "pistachios": "pistachio",
    "hazelnuts": "hazelnut",
    "macadamia-nuts": "macadamia",
    "brazil-nuts": "brazil_nut",
    "mustard": "mustard",
    "חרדל": "mustard",
    "celery": "celery",
    "סלרי": "celery",
    "lupin": "lupin",
    "לופין": "lupin",
    "sulphur-dioxide-and-sulphites": "sulphites",
    "sulphites": "sulphites",
    "סולפיטים": "sulphites",
}


@dataclass(frozen=True)
class OffProduct:
    barcode: str
    name: str | None
    brands: str | None
    ingredients_text: str | None
    image_url: str | None
    allergen_ids: tuple[str, ...]
    trace_ids: tuple[str, ...]
    unmapped_tags: tuple[str, ...] = ()


def _strip_tag(tag: str) -> str:
    """מסיר את קידומת השפה מהתגית ומשאיר את הערך עצמו."""
    value = tag.split(":", 1)[-1] if ":" in tag else tag
    return value.strip().lower()


def map_tags(tags: list[str] | None) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """ממפה תגיות לרשימה הסגורה. מחזיר גם את מה שלא זוהה."""
    mapped: dict[str, None] = {}
    unmapped: dict[str, None] = {}
    for tag in tags or []:
        key = _strip_tag(tag)
        allergen_id = _TAG_TO_ALLERGEN.get(key)
        if allergen_id is None:
            allergen_id = _TAG_TO_ALLERGEN.get(hebrew.normalize(key))
        if allergen_id:
            mapped.setdefault(allergen_id, None)
        elif key:
            unmapped.setdefault(key, None)
    return tuple(mapped), tuple(unmapped)


def parse_product(payload: dict) -> OffProduct | None:
    """הופך תשובת API אחת למוצר. מחזיר None כשהמוצר לא נמצא."""
    if payload.get("status") != 1:
        return None
    product = payload.get("product") or {}
    barcode = str(product.get("code") or "")
    if not barcode:
        return None

    allergen_ids, unmapped_allergens = map_tags(product.get("allergens_tags"))
    trace_ids, unmapped_traces = map_tags(product.get("traces_tags"))

    return OffProduct(
        barcode=barcode,
        name=product.get("product_name_he") or product.get("product_name"),
        brands=product.get("brands"),
        ingredients_text=(
            product.get("ingredients_text_he") or product.get("ingredients_text")
        ),
        image_url=product.get("image_front_url"),
        allergen_ids=allergen_ids,
        trace_ids=trace_ids,
        unmapped_tags=unmapped_allergens + unmapped_traces,
    )


def to_claims(product: OffProduct, observed_on: date) -> list[AllergenClaim]:
    """קביעות מפורשות. שני השדות נפרדים במקור, ולכן הרמה אינה נגזרת.

    אלרגן שמופיע בשני השדות נחשב מכיל: זו הרמה המחמירה מבין השתיים.
    """
    claims: list[AllergenClaim] = []
    contains = set(product.allergen_ids)

    for allergen_id in product.allergen_ids:
        claims.append(
            AllergenClaim(
                allergen_id=allergen_id,
                level=Level.CONTAINS,
                source=Source.OPEN_FOOD_FACTS,
                observed_on=observed_on,
                source_ref=f"off:{product.barcode}",
            )
        )
    for allergen_id in product.trace_ids:
        if allergen_id in contains:
            continue
        claims.append(
            AllergenClaim(
                allergen_id=allergen_id,
                level=Level.MAY_CONTAIN,
                source=Source.OPEN_FOOD_FACTS,
                observed_on=observed_on,
                source_ref=f"off:{product.barcode}",
            )
        )
    return claims
