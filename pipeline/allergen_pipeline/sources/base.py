"""חוזה משותף לכל מתאמי המקורות, ובדיקות השפיות שמגנות על המאגר.

כל רשת וכל יצרן מממשים את הפרסום שלהם אחרת, ולכן לכל משפחת מקורות
מתאם נפרד. מה שמשותף הוא ההתנהגות כשמשהו משתבש: ריצה שנכשלה בבדיקת
שפיות אינה דורסת נתונים תקינים, וכישלון במקור אלרגנים לעולם אינו מחזיר
מוצר למצב אין מידע.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Generic, Protocol, TypeVar

T = TypeVar("T")

# ריצה שמחזירה פחות מהשיעור הזה מהריצה הקודמת נחשבת חשודה.
MIN_ROW_RATIO = 0.7

# שיעור השורות המינימלי שבו שדות החובה מלאים.
MIN_REQUIRED_FIELD_RATIO = 0.9

# מתאם ששותק יותר מזה מייצר התראה. שקט אינו חדשות טובות.
STALENESS_ALERT_AFTER = timedelta(days=7)


class SanityCheckFailed(Exception):
    """ריצה שנפסלה. הנתונים הקיימים נשארים כמות שהם."""


@dataclass(frozen=True)
class RunStats:
    adapter_id: str
    rows: int
    started_at: datetime
    finished_at: datetime
    missing_required: int = 0

    @property
    def required_field_ratio(self) -> float:
        if self.rows == 0:
            return 0.0
        return (self.rows - self.missing_required) / self.rows


@dataclass
class RunResult(Generic[T]):
    """תוצאת ריצה אחת של מתאם."""

    adapter_id: str
    items: list[T] = field(default_factory=list)
    stats: RunStats | None = None
    accepted: bool = False
    rejection_reason: str | None = None


def check_run(
    stats: RunStats,
    previous_rows: int | None = None,
    min_row_ratio: float = MIN_ROW_RATIO,
    min_required_ratio: float = MIN_REQUIRED_FIELD_RATIO,
) -> None:
    """פוסל ריצה שנראית שבורה. מרים חריגה ולא מחזיר ערך.

    נועד לתפוס את המקרה שבו רשת שינתה פורמט או שהגירוד נחסם, ובמקום
    שגיאה ברורה חוזרות מעט שורות או שורות חסרות שדות.
    """
    if stats.rows == 0:
        raise SanityCheckFailed(
            f"{stats.adapter_id}: הריצה לא החזירה שורות כלל"
        )

    if previous_rows:
        ratio = stats.rows / previous_rows
        if ratio < min_row_ratio:
            raise SanityCheckFailed(
                f"{stats.adapter_id}: {stats.rows} שורות מול {previous_rows} "
                f"בריצה הקודמת ({ratio:.0%}). חשד לשינוי פורמט או לחסימה."
            )

    if stats.required_field_ratio < min_required_ratio:
        raise SanityCheckFailed(
            f"{stats.adapter_id}: רק {stats.required_field_ratio:.0%} מהשורות "
            "מכילות את כל שדות החובה."
        )


def is_stale(last_success: date | None, today: date) -> bool:
    """האם המתאם שותק מספיק זמן כדי להצדיק התראה."""
    if last_success is None:
        return True
    return today - last_success > STALENESS_ALERT_AFTER


class SourceAdapter(Protocol[T]):
    """מתאם מקור אחד."""

    adapter_id: str

    def fetch(self) -> RunResult[T]:
        """מושך את הנתונים ומחזיר תוצאת ריצה שעברה בדיקת שפיות."""
        ...
