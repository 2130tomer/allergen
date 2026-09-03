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
    RETAILER = "retailer"
    OPEN_FOOD_FACTS = "open_food_facts"
    LABEL_EXTRACTION = "label_extraction"
    USER = "user"

    @property
    def label_he(self) -> str:
        return _SOURCE_LABELS[self]

    @property
    def may_assert_absence(self) -> bool:
        """רק הצהרת יצרן רשמית רשאית לשלול אלרגן. ראו ADR-0002.

        קמעונאי אינו רשאי, גם כשהמידע שלו מפורט יותר משל היצרן. הוא
        מעתיק תווית, ואינו האחראי עליה.
        """
        return self is Source.MANUFACTURER


_SOURCE_LABELS = {
    Source.MANUFACTURER: "אתר היצרן",
    Source.RETAILER: "אתר הרשת",
    Source.OPEN_FOOD_FACTS: "Open Food Facts",
    Source.LABEL_EXTRACTION: "חילוץ מתמונת תווית",
    Source.USER: "דיווח משתמש",
}

# דרגת האמינות של המקור. גבוה יותר = אמין יותר. ראו ADR-0006 להסבר
# מדוע הקמעונאי יושב מעל Open Food Facts ומתחת ליצרן.
_TIER = {
    Source.MANUFACTURER: 5,
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
