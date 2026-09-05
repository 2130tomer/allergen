"""קביעת אלרגן: טענה בודדת ממקור אחד, בתאריך אחד.

מוצר מחזיק אוסף של קביעות מכמה מקורות, שעשויות לסתור זו את זו.
ההכרעה ביניהן היא באחריות resolution.py ולא נשמרת כערך יחיד.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import Enum


class Level(str, Enum):
    """רמת היחס בין מוצר לאלרגן."""

    CONTAINS = "contains"
    MAY_CONTAIN = "may_contain"
    ABSENT = "absent"
    UNKNOWN = "unknown"

    @property
    def label_he(self) -> str:
        return _LEVEL_LABELS[self]

    @property
    def is_positive(self) -> bool:
        """האם הרמה מצהירה על נוכחות אלרגן, ולו אפשרית."""
        return self in (Level.CONTAINS, Level.MAY_CONTAIN)


_LEVEL_LABELS = {
    Level.CONTAINS: "מכיל",
    Level.MAY_CONTAIN: "עלול להכיל",
    Level.ABSENT: "לא מכיל",
    Level.UNKNOWN: "אין מידע",
}

# חומרת הרמות. משמש להכרעה מחמירה בין קביעות שוות אמינות.
_SEVERITY = {
    Level.UNKNOWN: 0,
    Level.ABSENT: 1,
    Level.MAY_CONTAIN: 2,
    Level.CONTAINS: 3,
}


def stricter(first: Level, second: Level) -> Level:
    """הרמה המחמירה מבין השתיים."""
    return first if _SEVERITY[first] >= _SEVERITY[second] else second


class Source(str, Enum):
    """הגורם שממנו הגיעה הקביעה."""

    MANUFACTURER = "manufacturer"
    DECLARED_FREE_FROM = "declared_free_from"
    RETAILER = "retailer"
    OPEN_FOOD_FACTS = "open_food_facts"
    LABEL_EXTRACTION = "label_extraction"
    USER = "user"

    @property
    def label_he(self) -> str:
        return _SOURCE_LABELS[self]

    @property
    def may_assert_absence(self) -> bool:
        """מי רשאי לשלול אלרגן. ראו ADR-0002 ו-ADR-0007.

        שני מקורות בלבד. הראשון הוא הצהרת היצרן. השני הוא הצהרת "ללא"
        מפורשת המודפסת על האריזה — היא אמנם מגיעה אלינו דרך הקמעונאי,
        אך היא אינה שלו: היא טענה מוסדרת של היצרן, שהוא נושא באחריות
        עליה, והקמעונאי רק מעתיק אותה.

        קמעונאי אינו רשאי לשלול אלרגן בכל דרך אחרת, גם כשהמידע שלו
        מפורט יותר משל היצרן. הוא מעתיק תווית, ואינו האחראי עליה.

        היעדר ראיה לעולם אינו ראיה להיעדר: שום מקור אינו רשאי לקבוע
        ABSENT רק משום שהאלרגן לא הופיע ברשימה.
        """
        return self in (Source.MANUFACTURER, Source.DECLARED_FREE_FROM)


_SOURCE_LABELS = {
    Source.MANUFACTURER: "אתר היצרן",
    Source.DECLARED_FREE_FROM: "הצהרת \"ללא\" על האריזה",
    Source.RETAILER: "אתר הרשת",
    Source.OPEN_FOOD_FACTS: "Open Food Facts",
    Source.LABEL_EXTRACTION: "חילוץ מתמונת תווית",
    Source.USER: "דיווח משתמש",
}

# דרגת האמינות של המקור. גבוה יותר = אמין יותר. ראו ADR-0006 להסבר
# מדוע הקמעונאי יושב מעל Open Food Facts ומתחת ליצרן.
_TIER = {
    Source.MANUFACTURER: 5,
    Source.DECLARED_FREE_FROM: 5,
    Source.RETAILER: 4,
    Source.OPEN_FOOD_FACTS: 3,
    Source.LABEL_EXTRACTION: 2,
    Source.USER: 1,
}


def confidence_tier(source: Source) -> int:
    return _TIER[source]


@dataclass(frozen=True)
class AllergenClaim:
    """טענה שמוצר נמצא ברמה מסוימת ביחס לאלרגן, לפי מקור ותאריך."""

    allergen_id: str
    level: Level
    source: Source
    observed_on: date
    source_ref: str | None = None
    # נכון כשהרמה נגזרה מפירוק רשימה שטוחה ולא נאמרה במפורש במקור.
    level_inferred: bool = False

    def __post_init__(self) -> None:
        if self.level is Level.ABSENT and not self.source.may_assert_absence:
            raise ValueError(
                f"מקור {self.source.value} אינו רשאי לקבוע היעדר אלרגן (ADR-0002)"
            )
