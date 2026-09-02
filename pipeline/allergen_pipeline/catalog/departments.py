"""עץ המחלקות הקנוני, בשתי רמות, וסיווג מוצרים אליו.

העץ שלנו ולא של הרשתות: נתוני הקטגוריות בקבצי שקיפות המחירים אינם
עקביים בין רשת לרשת ולעיתים חסרים לגמרי. הסיווג מבוסס כללי מילות
מפתח על שם המוצר, ומה שלא נתפס נשאר במחלקה גלויה של לא מסווג במקום
להיזרק בשקט לאחר.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..text import hebrew

UNCLASSIFIED_ID = "unclassified"


@dataclass(frozen=True)
class Department:
    id: str
    label_he: str
    parent_id: str | None = None


@dataclass(frozen=True)
class _Rule:
    department_id: str
    keywords: tuple[str, ...]


_TREE: tuple[Department, ...] = (
    Department("dairy", "חלב וביצים"),
    Department("dairy_milk", "חלב ומשקאות חלב", "dairy"),
    Department("dairy_cheese", "גבינות", "dairy"),
    Department("dairy_yogurt", "יוגורט ומעדנים", "dairy"),
    Department("dairy_butter", "חמאה ושמנת", "dairy"),
    Department("dairy_eggs", "ביצים", "dairy"),
    Department("bakery", "לחם ומאפים"),
    Department("bakery_bread", "לחמים", "bakery"),
    Department("bakery_rolls", "לחמניות ופיתות", "bakery"),
    Department("bakery_pastry", "מאפים ועוגות", "bakery"),
    Department("bakery_crackers", "קרקרים ולחמיות", "bakery"),
    Department("beverages", "משקאות"),
    Department("beverages_water", "מים ומים מוגזים", "beverages"),
    Department("beverages_soft", "משקאות קלים", "beverages"),
    Department("beverages_juice", "מיצים", "beverages"),
    Department("beverages_hot", "קפה תה ושוקו", "beverages"),
    Department("beverages_alcohol", "אלכוהול", "beverages"),
    Department("snacks", "חטיפים ומתוקים"),
    Department("snacks_salty", "חטיפים מלוחים", "snacks"),
    Department("snacks_chocolate", "שוקולד", "snacks"),
    Department("snacks_candy", "ממתקים", "snacks"),
    Department("snacks_cookies", "עוגיות ובופלות", "snacks"),
    Department("snacks_nuts", "פיצוחים ואגוזים", "snacks"),
    Department("meat_fish", "בשר ודגים"),
    Department("meat_fresh", "בשר ועוף טרי", "meat_fish"),
    Department("meat_processed", "נקניקים ובשר מעובד", "meat_fish"),
    Department("fish_fresh", "דגים", "meat_fish"),
    Department("frozen", "קפואים"),
    Department("frozen_vegetables", "ירקות קפואים", "frozen"),
    Department("frozen_ready", "מוכן ומבושל קפוא", "frozen"),
    Department("frozen_desserts", "גלידות וקינוחים קפואים", "frozen"),
    Department("pantry", "יבשים ודגנים"),
    Department("pantry_pasta", "פסטה ואטריות", "pantry"),
    Department("pantry_rice", "אורז וקטניות", "pantry"),
    Department("pantry_flour", "קמחים ואפייה", "pantry"),
    Department("pantry_cereal", "דגני בוקר", "pantry"),
    Department("canned", "שימורים ומטבלים"),
    Department("canned_vegetables", "שימורי ירקות", "canned"),
    Department("canned_fish", "שימורי דגים", "canned"),
    Department("canned_spreads", "ממרחים וסלטים", "canned"),
    Department("condiments", "רטבים ותבלינים"),
    Department("condiments_sauces", "רטבים", "condiments"),
    Department("condiments_spices", "תבלינים", "condiments"),
    Department("oils", "שמנים וחומץ"),
    Department("produce", "פירות וירקות"),
    Department("baby", "מזון תינוקות"),
    Department("baby_formula", "תמל ותחליפי חלב", "baby"),
    Department("baby_food", "מזון לתינוקות", "baby"),
    Department("health", "בריאות ותוספי תזונה"),
    Department("health_free_from", "ללא גלוטן וטבעוני", "health"),
    Department(UNCLASSIFIED_ID, "לא מסווג"),
)

DEPARTMENTS: dict[str, Department] = {d.id: d for d in _TREE}


def top_level() -> tuple[Department, ...]:
    return tuple(d for d in _TREE if d.parent_id is None)


def children_of(parent_id: str) -> tuple[Department, ...]:
    return tuple(d for d in _TREE if d.parent_id == parent_id)


def get(department_id: str) -> Department:
    return DEPARTMENTS[department_id]


# ספציפי קודם. הכלל הראשון שמתאים מנצח.
_RULES: tuple[_Rule, ...] = (
    _Rule("baby_formula", ("תמל", "מטרנה", "סימילאק", "נוטרילון", "תחליף חלב אם")),
    _Rule("baby_food", ("מזון תינוקות", "גרבר", "מחית לתינוק", "דייסת תינוקות")),
    _Rule("dairy_eggs", ("ביצים", "ביצי חופש", "ביצה")),
    _Rule(
        "dairy_cheese",
        ("גבינה", "גבינת", "קוטג", "מוצרלה", "צהובה", "בולגרית", "פטה"),
    ),
    _Rule("dairy_yogurt", ("יוגורט", "מעדן", "דנונה", "אשל", "גיל")),
    _Rule("dairy_butter", ("חמאה", "שמנת", "ממרח חמאה")),
    _Rule("dairy_milk", ("חלב", "משקה חלב", "שוקו", "רוויון")),
    _Rule(
        "snacks_salty",
        ("במבה", "ביסלי", "אפרופו", "דוריטוס", "תפוציפס", "חטיף תירס", "חטיף מלוח"),
    ),
    _Rule("snacks_chocolate", ("שוקולד", "פרה", "קליק", "מקופלת", "טורטית")),
    _Rule("snacks_cookies", ("עוגיות", "בופלה", "ופל", "עוגיית", "פתיבר", "לוטוס")),
    _Rule(
        "snacks_nuts",
        ("פיצוחים", "גרעינים", "אגוזים", "שקדים", "קשיו", "פיסטוק", "בוטנים"),
    ),
    _Rule("snacks_candy", ("סוכריות", "מסטיק", "טופי", "ממתק", "סוכריה")),
    _Rule("bakery_bread", ("לחם", "פרוס", "בגט", "חלה")),
    _Rule("bakery_rolls", ("לחמניה", "לחמניות", "פיתה", "פיתות", "לאפה")),
    _Rule("bakery_crackers", ("קרקר", "מצות", "לחמית", "פריכיות")),
    _Rule("bakery_pastry", ("עוגה", "מאפה", "בורקס", "קרואסון", "רוגלך")),
    _Rule(
        "beverages_water",
        ("מים מינרלים", "מים מוגזים", "סודה", "מי עדן", "נביעות"),
    ),
    _Rule(
        "beverages_soft",
        ("קולה", "ספרייט", "פאנטה", "משקה קל", "שוופס", "משקה אנרגיה"),
    ),
    _Rule("beverages_juice", ("מיץ", "נקטר", "פריגת", "טרופית")),
    _Rule("beverages_hot", ("קפה", "תה", "נמס", "אספרסו", "שוקו אבקה")),
    _Rule("beverages_alcohol", ("יין", "בירה", "וודקה", "ויסקי", "ערק", "משקה חריף")),
    _Rule("meat_processed", ("נקניק", "נקניקיה", "פסטרמה", "סלמי", "קבנוס")),
    _Rule("meat_fresh", ("עוף", "בשר", "שניצל", "כבש", "הודו", "אנטריקוט")),
    _Rule("fish_fresh", ("סלמון", "דניס", "לברק", "פילה דג", "מושט")),
    _Rule("canned_fish", ("טונה", "סרדינים", "אנשובי", "שימורי דגים")),
    _Rule("canned_vegetables", ("שימורי", "תירס משומר", "אפונה משומרת", "זיתים")),
    _Rule("canned_spreads", ("חומוס", "טחינה", "מטבל", "ממרח", "סלט חצילים")),
    _Rule("frozen_vegetables", ("ירקות קפואים", "אפונה קפואה", "תירס קפוא")),
    _Rule("frozen_desserts", ("גלידה", "ארטיק", "שלגון", "קרחון")),
    _Rule("frozen_ready", ("קפוא", "מאפה קפוא", "פיצה קפואה")),
    _Rule("pantry_pasta", ("פסטה", "ספגטי", "אטריות", "מקרוני", "פנה", "נודלס")),
    _Rule(
        "pantry_rice",
        ("אורז", "עדשים", "שעועית", "קטניות", "בורגול", "קינואה"),
    ),
    _Rule("pantry_flour", ("קמח", "אבקת אפייה", "סוכר", "שמרים", "תערובת אפייה")),
    _Rule("pantry_cereal", ("דגני בוקר", "קורנפלקס", "גרנולה", "שוגי")),
    _Rule(
        "condiments_sauces",
        ("קטשופ", "מיונז", "חרדל", "רוטב", "רוטב סויה", "חומץ בלסמי"),
    ),
    _Rule(
        "condiments_spices",
        ("תבלין", "פפריקה", "כמון", "מלח", "פלפל שחור", "אבקת מרק"),
    ),
    _Rule("oils", ("שמן", "חומץ", "שמן זית", "שמן קנולה")),
    _Rule("produce", ("עגבניות", "מלפפון", "בננות", "תפוחים", "בצל", "גזר", "חסה")),
    _Rule("health_free_from", ("ללא גלוטן", "טבעוני", "ללא לקטוז", "אורגני")),
)

_COMPILED_RULES: tuple[tuple[str, tuple[tuple[str, ...], ...]], ...] = tuple(
    (rule.department_id, tuple(tuple(hebrew.tokenize(kw)) for kw in rule.keywords))
    for rule in _RULES
)


def classify(product_name: str, manufacturer: str | None = None) -> str:
    """מחזיר מזהה תת-מחלקה, או לא מסווג כשאף כלל לא נתפס."""
    haystack = hebrew.tokenize(f"{product_name} {manufacturer or ''}")
    if not haystack:
        return UNCLASSIFIED_ID
    forms = [frozenset(hebrew.token_variants(token)) for token in haystack]

    for department_id, keyword_sets in _COMPILED_RULES:
        for keyword_tokens in keyword_sets:
            if not keyword_tokens:
                continue
            span = len(keyword_tokens)
            for start in range(len(forms) - span + 1):
                if all(
                    keyword_tokens[offset] in forms[start + offset]
                    for offset in range(span)
                ):
                    return department_id
    return UNCLASSIFIED_ID


def top_level_of(department_id: str) -> str:
    department = DEPARTMENTS.get(department_id)
    if department is None:
        return UNCLASSIFIED_ID
    return department.parent_id or department.id
