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
API_SEARCH_URL = "https://world.openfoodfacts.org/api/v2/search"

# ה-API מקבל כמה ברקודים מופרדים בפסיק בשאילתה אחת. בלי זה, העשרה של
# קטלוג בגודל אמיתי הייתה דורשת עשרות אלפי בקשות.
BATCH_SIZE = 50

USER_AGENT = "allergen-il/0.1 (allergen catalog for Israel)"

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

"""שמות אלרגנים בשפות שנצפו בפועל בתגיות של Open Food Facts.

המאגר גלובלי ובעל תרומה פתוחה, ולכן מוצר ישראלי אחד יכול לשאת תגיות
בעברית, אנגלית, רוסית, גרמנית, צרפתית או פולנית, לפי מי שהזין אותו.
תגית שלא זוהתה מדווחת ואינה נבלעת בשקט, כדי שהרשימה כאן תתרחב לפי
מה שבאמת מופיע ולא לפי ניחוש.
"""
_SYNONYMS: dict[str, tuple[str, ...]] = {
    "gluten": (
        "gluten", "גלוטן", "חיטה", "wheat", "blé", "ble", "trigo", "grano",
        "weizen", "пшеница", "pszenica", "glutine", "glutenhaltige getreidesorten",
        "barley", "orge", "gerste", "cebada", "ячмень", "jęczmień",
        "rye", "seigle", "roggen", "centeno", "рожь", "żyto",
        "oats", "avoine", "hafer", "avena", "овес", "owies",
        "céréales contenant du gluten", "lepek",
    ),
    "milk": (
        "milk", "חלב", "lait", "leche", "latte", "milch", "молоко", "mleko",
        "mleka", "mléko", "leite", "süt", "lactose", "laktoza", "lactosa",
        "сметана", "milchproteine", "produits laitiers", "dairy",
    ),
    "eggs": (
        "eggs", "egg", "ביצים", "oeuf", "oeufs", "œufs", "huevo", "huevos",
        "uova", "eier", "яйца", "jaja", "jaj", "vejce", "ovos",
    ),
    "peanuts": (
        "peanuts", "peanut", "בוטנים", "arachide", "arachides", "cacahuete",
        "cacahuètes", "cacahuetes", "erdnüsse", "erdnuss", "арахис",
        "orzeszki ziemne", "amendoim", "arachidi",
    ),
    "soy": (
        "soybeans", "soy", "soya", "סויה", "soja", "soia", "соя", "sója",
        "sojabohnen",
    ),
    "sesame": (
        "sesame-seeds", "sesame", "שומשום", "sésame", "sesamo", "sesam",
        "ajonjolí", "кунжут", "sezam", "sesamsamen",
    ),
    "fish": (
        "fish", "דגים", "poisson", "poissons", "pescado", "pesce", "fisch",
        "рыба", "ryby", "peixe",
    ),
    "crustaceans": (
        "crustaceans", "סרטנים", "crustacés", "crustaceos", "crustáceos",
        "crostacei", "krebstiere", "ракообразные", "skorupiaki",
    ),
    "molluscs": (
        "molluscs", "רכיכות", "mollusques", "moluscos", "molluschi",
        "weichtiere", "моллюски", "mięczaki",
    ),
    allergens.TREE_NUTS_ID: (
        "nuts", "tree-nuts", "אגוזים", "fruits à coque", "fruits a coque",
        "noix", "nueces", "nüsse", "орехи", "orzechy", "frutos secos",
    ),
    "almond": ("almonds", "almond", "שקדים", "amande", "amandes", "almendra", "mandeln", "миндаль", "migdały"),
    "walnut": ("walnuts", "walnut", "אגוזי מלך", "nuez", "walnüsse", "грецкие орехи"),
    "cashew": ("cashew", "cashew-nuts", "קשיו", "noix de cajou", "anacardo", "cashewnüsse", "кешью", "nerkowce"),
    "pecan": ("pecan-nuts", "pecan", "פקאן", "noix de pécan"),
    "pistachio": ("pistachio", "pistachios", "פיסטוק", "pistache", "pistacho", "pistazien", "фисташки", "pistacje"),
    "hazelnut": ("hazelnuts", "hazelnut", "אגוזי לוז", "noisette", "noisettes", "avellana", "haselnüsse", "фундук"),
    "macadamia": ("macadamia-nuts", "macadamia", "מקדמיה"),
    "brazil_nut": ("brazil-nuts", "brazil-nut", "אגוזי ברזיל", "noix du brésil"),
    "mustard": ("mustard", "חרדל", "moutarde", "mostaza", "senape", "senf", "горчица", "gorczyca"),
    "celery": ("celery", "סלרי", "céleri", "celeri", "apio", "sedano", "sellerie", "сельдерей", "seler"),
    "lupin": ("lupin", "לופין", "lupino", "lupine", "łubin", "altramuces"),
    "sulphites": (
        "sulphur-dioxide-and-sulphites", "sulphites", "sulfites", "סולפיטים",
        "sulfitos", "solfiti", "sulfite", "schwefeldioxid", "сульфиты",
        "siarczyny", "anhydride sulfureux et sulfites", "dióxido de azufre y sulfitos",
    ),
}

# מהתגית של Open Food Facts אל הרשימה הסגורה שלנו.
_TAG_TO_ALLERGEN: dict[str, str] = {
    synonym: allergen_id
    for allergen_id, synonyms in _SYNONYMS.items()
    for synonym in synonyms
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


def parse_search_payload(payload: dict) -> list[OffProduct]:
    """הופך תשובת חיפוש מרובת מוצרים לרשימת מוצרים."""
    products: list[OffProduct] = []
    for raw in payload.get("products") or []:
        parsed = parse_product({"status": 1, "product": raw})
        if parsed is not None:
            products.append(parsed)
    return products


class ProductNotFound(Exception):
    """המוצר אינו במאגר. אין מידע, ולא היעדר אלרגנים."""


def fetch_one(client, barcode: str) -> OffProduct | None:
    """מושך מוצר אחד.

    נקודת הקצה הזו יציבה, בניגוד לחיפוש המרובה שמחזיר 503 באופן קבוע.
    מדידה על נתונים אמיתיים: כ-0.23 שניות לבקשה, בלי כשלים.

    מחזיר None כשהמוצר אינו קיים; זה מצב תקין ולא שגיאה.
    """
    response = client.get(
        API_PRODUCT_URL.format(barcode=barcode),
        params={"fields": ",".join(FIELDS)},
    )
    if response.status_code == 404:
        return None
    response.raise_for_status()
    return parse_product(response.json())


def fetch_batch(client, barcodes: list[str]) -> list[OffProduct]:
    """מושך קבוצת ברקודים בבקשה אחת.

    נשמר לשלמות, אך אינו בשימוש בצינור: נקודת הקצה של החיפוש המרובה
    מחזירה 503 באופן קבוע. השתמשו ב-fetch_one עם מקביליות.
    """
    if not barcodes:
        return []
    response = client.get(
        API_SEARCH_URL,
        params={
            "code": ",".join(barcodes),
            "fields": ",".join(FIELDS),
            "page_size": len(barcodes),
        },
    )
    response.raise_for_status()
    return parse_search_payload(response.json())


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
