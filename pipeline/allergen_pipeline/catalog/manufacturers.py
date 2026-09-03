"""מיפוי יצרני המזון והמשקאות בישראל.

שמות היצרנים בקבצי שקיפות המחירים הם טקסט חופשי שהוקלד על ידי הרשתות,
ולכן אותה חברה מופיעה בכמה צורות: "שטראוס גרופ בע\"מ", "שטראוס בריאות
בע\"מ", "גלידת שטראוס בע\"מ" ו"שטראוס פריטו ליי בע\"מ" הן ארבע רשומות
של אותה קבוצה. בנוסף, חלק מהערכים אינם שמות יצרן כלל אלא ממלאי מקום
כמו "כללי" ו"שונות".

המודול הזה עושה שלושה דברים: מנרמל שם, מזהה ממלאי מקום, וממפה שם
לקבוצה תאגידית. המיפוי לקבוצות מתוחזק ידנית, מאותה סיבה שמיפוי הרכיבים
מתוחזק ידנית: ניחוש כאן מייצר איחוד שגוי בין חברות שאינן קשורות.

המטרה המעשית היא לדעת לאיזה יצרנים כדאי לבנות מתאם. יצרן שמכסה מאתיים
מוצרים בקטלוג שווה מתאם; יצרן עם מוצר אחד לא.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from ..text import hebrew

"""סיומות משפטיות שאינן חלק מהשם.

הצורות כאן הן **אחרי** נרמול עברי, ולא כפי שהן נכתבות בקובץ. הנרמול
מסיר גרשיים בלי להוסיף רווח, ולכן בע"מ הופך ל-בעמ ואגש"ח הופך ל-אגשח.
הסדר הזה חשוב: ניסיון להסיר את הסיומת לפני הנרמול נכשל, כי הסרת
הפיסוק כבר פירקה אותה לשתי מילים.
"""
_LEGAL_SUFFIXES = (
    "בעמ",
    "אגשח",
    "אגודה שיתופית חקלאית",
    "אגודה שיתופית",
    "ltd",
    "limited",
    "inc",
    "llc",
    "gmbh",
    "spa",
    "sa",
)

# ערכים שאינם שם יצרן. הרשתות ממלאות אותם כשאין להן את המידע.
_PLACEHOLDERS = frozenset(
    {
        "כללי",
        "כללית",
        "שונות",
        "שונים",
        "אחר",
        "אחרים",
        "לא ידוע",
        "ללא",
        "ללא יצרן",
        "יבואן",
        "כללי אחר",
        "general",
        "other",
        "unknown",
        "n/a",
    }
)

_WHITESPACE = re.compile(r"\s+")


@dataclass(frozen=True)
class ManufacturerGroup:
    """קבוצה תאגידית אחת, ואיך מזהים אותה.

    שדה website מכיל רק כתובות שנבדקו והחזירו 200. כתובת שלא אומתה
    נשארת None במכוון: מרשם עם כתובות שגויות גרוע ממרשם שמודה שאינו
    יודע, כי הוא שולח את מי שיקרא אותו לרדוף אחרי דומיינים שאינם
    קיימים.
    """

    id: str
    name_he: str
    # מילות מפתח שמופיעות בשמות של חברות הקבוצה, אחרי נרמול.
    keywords: tuple[str, ...]
    website: str | None = None
    # האם האתר מפרסם אלרגנים ברמת מוצר, כפי שנבדק בפועל.
    # None = לא נבדק. False = נבדק ואינו מפרסם.
    publishes_allergens: bool | None = None
    notes: str | None = None


"""הקבוצות התאגידיות הגדולות בשוק המזון הישראלי.

הרשימה נגזרה מהשמות שנצפו בפועל בקטלוג, ולא מרשימה חיצונית. היא
מסודרת לפי משקל בקטלוג ולא לפי גודל החברה בשוק, כי מה שמעניין אותנו
הוא כמה מוצרים מתאם יכסה.
"""
GROUPS: tuple[ManufacturerGroup, ...] = (
    ManufacturerGroup(
        id="tnuva",
        name_he="תנובה",
        keywords=("תנובה",),
        website="https://www.tnuva.co.il",
    ),
    ManufacturerGroup(
        id="osem_nestle",
        name_he="אסם-נסטלה",
        keywords=("אסם", "נסטלה", "עלית מוצרי", "טבעול", "מטרנה", "סבן"),
        website="https://www.osem-nestle.co.il",
        publishes_allergens=True,
        notes="מפרסם רשימה שטוחה בלי הבחנה בין מכיל לעלול להכיל. ראו ADR-0004.",
    ),
    ManufacturerGroup(
        id="strauss",
        name_he="שטראוס",
        keywords=("שטראוס", "עלית", "מקס ברנר", "יטבתה", "צבר"),
        website="https://www.strauss-group.co.il",
        publishes_allergens=False,
        notes=(
            "נבדק. האתר מסביר מהם אלרגנים אך אינו מפרסם אותם לכל מוצר. "
            "עמודי המוצר הם עמודי מותג בלי ברקוד ובלי רשימת רכיבים."
        ),
    ),
    ManufacturerGroup(
        id="unilever",
        name_he="יוניליוור ישראל",
        keywords=("יוניליוור", "תלמה", "בייגל בייגל", "קליק"),
        website=None,
    ),
    ManufacturerGroup(
        id="yafora",
        name_he="יפאורה-תבורי",
        keywords=("יפאורה", "תבורי"),
        website=None,
    ),
    ManufacturerGroup(
        id="central_bottling",
        name_he="החברה המרכזית למשקאות",
        keywords=("החברה המרכזית", "קוקה קולה", "נביעות", "פריגת", "תפוגן"),
        website=None,
    ),
    ManufacturerGroup(
        id="sugat",
        name_he="סוגת",
        keywords=("סוגת",),
        website="https://www.sugat.com",
    ),
    ManufacturerGroup(
        id="zoglobek",
        name_he="זוגלובק",
        keywords=("זוגלובק",),
        website=None,
    ),
    ManufacturerGroup(
        id="of_tov",
        name_he="עוף טוב",
        keywords=("עוף טוב", "מוצרי עוף טוב"),
        website="https://oftov.co.il",
    ),
    ManufacturerGroup(
        id="tara",
        name_he="טרה",
        keywords=("טרה", "מחלבות טרה"),
        website=None,
    ),
    ManufacturerGroup(
        id="gad_dairies",
        name_he="מחלבות גד",
        keywords=("מחלבות גד", "מחלבת גד"),
        website=None,
    ),
    ManufacturerGroup(
        id="wissotzky",
        name_he="ויסוצקי",
        keywords=("ויסוצקי",),
        website=None,
    ),
    ManufacturerGroup(
        id="beit_hashita",
        name_he="בית השיטה",
        keywords=("בית השיטה", "בית-השיטה"),
        website=None,
    ),
    ManufacturerGroup(
        id="yavne",
        name_he="קבוצת יבנה",
        keywords=("קבוצת יבנה", "יבנה"),
        website=None,
    ),
    ManufacturerGroup(
        id="sunfrost",
        name_he="סנפרוסט",
        keywords=("סנפרוסט", "סאן פרוסט"),
        website=None,
    ),
    ManufacturerGroup(
        id="prigat",
        name_he="פריניר",
        keywords=("פריניר",),
        website=None,
    ),
    ManufacturerGroup(
        id="shamir_salads",
        name_he="סלטי שמיר",
        keywords=("סלטי שמיר", "שמיר סלטים"),
        website="https://www.shamirsalads.co.il",
    ),
    ManufacturerGroup(
        id="angel",
        name_he="מאפיית אנגל",
        keywords=("אנגל", "מאפיית שלמה א אנגל"),
        website=None,
    ),
    ManufacturerGroup(
        id="berman",
        name_he="מאפיית ברמן",
        keywords=("ברמן",),
        website=None,
    ),
    ManufacturerGroup(
        id="ferrero",
        name_he="פררו",
        keywords=("פררו",),
        website=None,
    ),
)


def strip_legal_suffix(normalized: str) -> str:
    """מסיר סיומות משפטיות מטקסט שכבר עבר נרמול עברי.

    ההסרה היא של מילה שלמה בלבד, כדי ש-inc לא יחתוך את "אינקובטור".
    """
    result = normalized
    for suffix in _LEGAL_SUFFIXES:
        pattern = re.compile(rf"(?:^|\s){re.escape(suffix)}(?=\s|$)")
        result = pattern.sub(" ", result)
    return _WHITESPACE.sub(" ", result).strip()


def normalize_name(raw: str | None) -> str:
    """צורה קנונית להשוואה בין שמות יצרן.

    הנרמול העברי רץ ראשון והסרת הסיומות אחריו. הסדר ההפוך אינו עובד:
    הנרמול מפרק את הפיסוק, וסיומת שכתובה בגרשיים כבר לא תזוהה.
    """
    if not raw:
        return ""
    return strip_legal_suffix(hebrew.normalize(raw))


def is_placeholder(raw: str | None) -> bool:
    """האם הערך אינו שם יצרן אלא ממלא מקום.

    "כללי" ו"שונות" מופיעים במאות מוצרים ואינם חברה. שיוך שלהם לקבוצה
    או הצגה שלהם כיצרן היא הטעיה של המשתמש.
    """
    if not raw:
        return True
    normalized = hebrew.normalize(raw)
    if not normalized:
        return True
    return any(
        normalized == hebrew.normalize(placeholder) for placeholder in _PLACEHOLDERS
    )


_COMPILED_GROUPS: tuple[tuple[ManufacturerGroup, tuple[str, ...]], ...] = tuple(
    (group, tuple(hebrew.normalize(keyword) for keyword in group.keywords))
    for group in GROUPS
)


def group_of(raw: str | None) -> ManufacturerGroup | None:
    """הקבוצה התאגידית של שם יצרן, אם היא מוכרת.

    ההתאמה היא על מילה שלמה ולא על תת-מחרוזת, כדי ש"עלית" לא יתפוס
    "מעלית" ו"טרה" לא יתפוס "טרהוילג".
    """
    if is_placeholder(raw):
        return None
    tokens = normalize_name(raw).split()
    if not tokens:
        return None

    for group, keywords in _COMPILED_GROUPS:
        for keyword in keywords:
            if _contains_phrase(tokens, keyword.split()):
                return group
    return None


def _contains_phrase(tokens: list[str], phrase: list[str]) -> bool:
    span = len(phrase)
    if span == 0 or span > len(tokens):
        return False
    return any(
        tokens[start : start + span] == phrase
        for start in range(len(tokens) - span + 1)
    )


@dataclass
class ManufacturerEntry:
    """שורה במרשם: שם קנוני, כמה מוצרים, ולאיזו קבוצה הוא שייך."""

    display_name: str
    normalized: str
    product_count: int = 0
    raw_names: set[str] = field(default_factory=set)
    group_id: str | None = None

    @property
    def group(self) -> ManufacturerGroup | None:
        if not self.group_id:
            return None
        return next((g for g in GROUPS if g.id == self.group_id), None)


def build_registry(
    names_with_counts: list[tuple[str, int]],
) -> list[ManufacturerEntry]:
    """בונה מרשם יצרנים ממוין לפי משקל בקטלוג.

    שמות שנורמלו לאותה צורה מאוחדים, וממלאי מקום מושמטים לגמרי.
    """
    by_normalized: dict[str, ManufacturerEntry] = {}

    for raw_name, count in names_with_counts:
        if is_placeholder(raw_name):
            continue
        normalized = normalize_name(raw_name)
        if not normalized:
            continue

        entry = by_normalized.get(normalized)
        if entry is None:
            group = group_of(raw_name)
            entry = ManufacturerEntry(
                display_name=raw_name.strip(),
                normalized=normalized,
                group_id=group.id if group else None,
            )
            by_normalized[normalized] = entry

        entry.product_count += count
        entry.raw_names.add(raw_name.strip())
        # השם המוצג הוא הצורה הנפוצה ביותר, כלומר הראשונה שנספרה הכי הרבה.
        if count > 0 and len(raw_name.strip()) < len(entry.display_name):
            entry.display_name = raw_name.strip()

    return sorted(
        by_normalized.values(), key=lambda e: e.product_count, reverse=True
    )


def group_totals(registry: list[ManufacturerEntry]) -> list[tuple[ManufacturerGroup, int]]:
    """סיכום לפי קבוצה תאגידית, ממוין לפי משקל בקטלוג."""
    totals: dict[str, int] = {}
    for entry in registry:
        if entry.group_id:
            totals[entry.group_id] = totals.get(entry.group_id, 0) + entry.product_count

    resolved = [
        (group, totals[group.id]) for group in GROUPS if group.id in totals
    ]
    return sorted(resolved, key=lambda item: item[1], reverse=True)
