"""הרשימה הסגורה של האלרגנים בני-הדיווח, וההיררכיה שביניהם.

הגרעין נגזר מתקנות סימון מזון ארוז מראש בישראל. סביבו נוספו רגישויות
שאינן אלרגיה קלאסית אך מחייבות אותה התנהגות סינון בדיוק — פול, לקטוז,
ותת-סוגי הדגן — כי למשתמש לא משנה מה השם הרפואי של המנגנון.

שני יחסים נפרדים מתקיימים כאן, וההפרדה ביניהם מכוונת:

יחס אב-בן (parent_id) הוא יחס הכלה טקסונומי, והוא זה שמעצב את הממשק:
בן מוצג מקונן תחת אביו. לכן קשיו יושב תחת אגוזי עץ, אך בוטנים אינם
יושבים תחת קטניות — למרות שבוטן הוא קטנית — כי קבורת הבוטנים בתוך
קטגוריה הייתה מסתירה את האלרגן המסוכן ביותר מאחורי הקלקה נוספת.

יחס הגרירה (_IMPLIES) הוא יחס בטיחות בלבד, ואינו מוצג. בחירת "קטניות"
גוררת בוטנים, סויה ולופין, כי מי שמסנן קטניות מתכוון גם להם. הגרירה
תמיד לכיוון המחמיר: היא מוסיפה אלרגנים לסינון ולעולם לא גורעת.

הכיוון ההפוך אסור במפורש: לקטוז אינו גורר חלב. חלב נטול לקטוז הוא
מוצר קיים ונפוץ, ומי שמסנן לקטוז אמור לראות אותו.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator

TREE_NUTS_ID = "tree_nuts"
GLUTEN_ID = "gluten"
LEGUMES_ID = "legumes"


@dataclass(frozen=True)
class Allergen:
    id: str
    label_he: str
    parent_id: str | None = None
    # הערה קצרה שמוצגת בממשק כשהשם לבדו אינו חד-משמעי.
    note_he: str | None = None

    @property
    def is_subtype(self) -> bool:
        return self.parent_id is not None


_ALLERGEN_LIST: tuple[Allergen, ...] = (
    # --- שמונת הגדולים של התקנות ---
    Allergen(GLUTEN_ID, "גלוטן"),
    Allergen("wheat", "חיטה", GLUTEN_ID),
    Allergen("barley", "שעורה", GLUTEN_ID),
    Allergen("rye", "שיפון", GLUTEN_ID),
    Allergen("oats", "שיבולת שועל", GLUTEN_ID),
    Allergen("spelt", "כוסמין", GLUTEN_ID),
    Allergen("milk", "חלב"),
    Allergen(
        "lactose",
        "לקטוז",
        note_he="רגישות לסוכר החלב. אינו זהה לאלרגיה לחלבון חלב.",
    ),
    Allergen("eggs", "ביצים"),
    Allergen("peanuts", "בוטנים"),
    Allergen("soy", "סויה"),
    Allergen("sesame", "שומשום"),
    Allergen("fish", "דגים"),
    Allergen("crustaceans", "סרטנים"),
    Allergen("molluscs", "רכיכות"),
    # --- אגוזי עץ ותת-סוגיהם ---
    Allergen(TREE_NUTS_ID, "אגוזי עץ"),
    Allergen("almond", "שקד", TREE_NUTS_ID),
    Allergen("walnut", "אגוז מלך", TREE_NUTS_ID),
    Allergen("cashew", "קשיו", TREE_NUTS_ID),
    Allergen("pecan", "פקאן", TREE_NUTS_ID),
    Allergen("pistachio", "פיסטוק", TREE_NUTS_ID),
    Allergen("hazelnut", "אגוז לוז", TREE_NUTS_ID),
    Allergen("macadamia", "מקדמיה", TREE_NUTS_ID),
    Allergen("brazil_nut", "אגוז ברזיל", TREE_NUTS_ID),
    Allergen("pine_nut", "צנוברים", TREE_NUTS_ID),
    Allergen("chestnut", "ערמונים", TREE_NUTS_ID),
    # --- קטניות ---
    Allergen(LEGUMES_ID, "קטניות"),
    Allergen(
        "fava_bean",
        "פול",
        LEGUMES_ID,
        note_he="רלוונטי לנשאי חסר G6PD (פאביזם).",
    ),
    Allergen("chickpea", "חומוס", LEGUMES_ID),
    Allergen("lentil", "עדשים", LEGUMES_ID),
    Allergen("pea", "אפונה", LEGUMES_ID),
    Allergen("bean", "שעועית", LEGUMES_ID),
    # --- שאר התקנות ---
    Allergen("mustard", "חרדל"),
    Allergen("celery", "סלרי"),
    Allergen("lupin", "לופין"),
    Allergen("sulphites", "סולפיטים"),
    # --- רגישויות נפוצות שאינן בתקנות ---
    Allergen("corn", "תירס"),
    Allergen("coconut", "קוקוס"),
    Allergen("sunflower", "חמניות"),
    Allergen("buckwheat", "כוסמת"),
    Allergen("gelatin", "ג'לטין"),
    Allergen("yeast", "שמרים"),
)

ALLERGENS: dict[str, Allergen] = {a.id: a for a in _ALLERGEN_LIST}

# גרירות בטיחות. המפתח נבחר, והערכים נוספים לסינון בשקט.
# ראו את הסבר ההפרדה בראש הקובץ.
_IMPLIES: dict[str, tuple[str, ...]] = {
    # בוטן, סויה ולופין הם קטניות, אך מוצגים בנפרד.
    LEGUMES_ID: ("peanuts", "soy", "lupin"),
}

# גרירת זיהוי: כשהאלרגן שמשמאל מזוהה במוצר, זה שמימין מזוהה איתו.
# נפרד לחלוטין מ-_IMPLIES, שעוסק בבחירת המשתמש ולא בתוכן המוצר.
#
# חלב גורר לקטוז כאן ולא ב-_IMPLIES, וההבדל מהותי. מוצר חלב רגיל אכן
# מכיל לקטוז, ולכן הגרירה שייכת לצד התוכן. היא נרשמת כמסקנה ולא
# כהצהרה, כך שהצהרת "נטול לקטוז" מפורשת על האריזה גוברת עליה — וחלב
# נטול לקטוז נשאר גלוי למי שמסנן לקטוז, כפי שנכון.
_CONTAINS_IMPLIES: dict[str, tuple[str, ...]] = {
    "milk": ("lactose",),
}


class UnknownAllergenError(KeyError):
    """מזהה אלרגן שאינו ברשימה הסגורה."""


def get(allergen_id: str) -> Allergen:
    try:
        return ALLERGENS[allergen_id]
    except KeyError as exc:
        raise UnknownAllergenError(allergen_id) from exc


def all_ids() -> tuple[str, ...]:
    return tuple(ALLERGENS)


def top_level_ids() -> tuple[str, ...]:
    return tuple(a.id for a in _ALLERGEN_LIST if a.parent_id is None)


def subtypes_of(parent_id: str) -> tuple[str, ...]:
    return tuple(a.id for a in _ALLERGEN_LIST if a.parent_id == parent_id)


def ancestors_of(allergen_id: str) -> tuple[str, ...]:
    """שרשרת ההורים של אלרגן, מהקרוב לרחוק."""
    chain: list[str] = []
    current = get(allergen_id).parent_id
    while current is not None:
        chain.append(current)
        current = get(current).parent_id
    return tuple(chain)


def implied_by(allergen_id: str) -> tuple[str, ...]:
    """האלרגנים שבחירת המזהה גוררת מטעמי בטיחות, ללא ההיררכיה."""
    return _IMPLIES.get(allergen_id, ())


def contains_implies(allergen_id: str) -> tuple[str, ...]:
    """האלרגנים שנוכחות המזהה במוצר גוררת את נוכחותם."""
    return _CONTAINS_IMPLIES.get(allergen_id, ())


def expand_detected(detected_ids: set[str]) -> set[str]:
    """הרחבת אלרגנים שזוהו לכל מה שנוכחותם מחייבת.

    שני כיוונים: עלייה בהיררכיה, כי חיטה שזוהתה היא גם גלוטן, וגרירת
    תוכן, כי חלב שזוהה הוא גם לקטוז. הכיוון ההפוך אינו נכון וגם אינו
    מתבצע: גלוטן שזוהה אינו מעיד על חיטה דווקא.
    """
    expanded = set(detected_ids)
    pending = list(detected_ids)
    while pending:
        current = pending.pop()
        for candidate in ancestors_of(current) + contains_implies(current):
            if candidate not in expanded:
                expanded.add(candidate)
                pending.append(candidate)
    return expanded


def expand_selection(selected_ids: set[str]) -> set[str]:
    """הרחבת בחירה לכל מה שהיא תופסת בפועל.

    שני מנגנונים פועלים כאן: ירידה בהיררכיה (אגוזי עץ תופס קשיו), וגרירת
    בטיחות (קטניות תופס בוטנים). שניהם מורחבים עד למיצוי, כדי שגרירה
    שנוחתת על אב תמשיך משם אל בניו.
    """
    expanded = set(selected_ids)
    pending = list(selected_ids)
    while pending:
        current = pending.pop()
        for candidate in subtypes_of(current) + implied_by(current):
            if candidate not in expanded:
                expanded.add(candidate)
                pending.append(candidate)
    return expanded


def iter_allergens() -> Iterator[Allergen]:
    return iter(_ALLERGEN_LIST)
