"""הרשתות שמהן נבנה הקטלוג, וכיצד מגיעים לקבצים שלהן.

התקנות מחייבות פרסום, אך לא מחייבות פורמט הפצה אחיד. חלק מהרשתות
מפרסמות פורטל ייעודי משלהן, ורובן משתמשות בפורטל המשותף שדורש שם
משתמש פומבי ללא סיסמה. הפרטים כאן הם תצורה ולא סוד.

סדר המימוש נגזר מגודל הקטלוג ומיציבות הפרסום: שופרסל ורמי לוי ראשונים.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class PortalKind(str, Enum):
    DEDICATED = "dedicated"
    PUBLISHED_PRICES = "published_prices"


@dataclass(frozen=True)
class Retailer:
    id: str
    name_he: str
    portal: PortalKind
    base_url: str
    username: str | None = None
    priority: int = 99

    @property
    def requires_login(self) -> bool:
        return self.portal is PortalKind.PUBLISHED_PRICES


RETAILERS: tuple[Retailer, ...] = (
    Retailer(
        id="shufersal",
        name_he="שופרסל",
        portal=PortalKind.DEDICATED,
        base_url="https://prices.shufersal.co.il/",
        priority=1,
    ),
    Retailer(
        id="rami_levy",
        name_he="רמי לוי",
        portal=PortalKind.PUBLISHED_PRICES,
        base_url="https://url.publishedprices.co.il/",
        username="RamiLevi",
        priority=2,
    ),
    Retailer(
        id="victory",
        name_he="ויקטורי",
        portal=PortalKind.PUBLISHED_PRICES,
        base_url="https://url.publishedprices.co.il/",
        username="Victory",
        priority=3,
    ),
    Retailer(
        id="yochananof",
        name_he="יוחננוף",
        portal=PortalKind.PUBLISHED_PRICES,
        base_url="https://url.publishedprices.co.il/",
        username="yohananof",
        priority=4,
    ),
    Retailer(
        id="hazi_hinam",
        name_he="חצי חינם",
        portal=PortalKind.PUBLISHED_PRICES,
        base_url="https://url.publishedprices.co.il/",
        username="HaziHinam",
        priority=5,
    ),
)

BY_ID: dict[str, Retailer] = {retailer.id: retailer for retailer in RETAILERS}


def in_priority_order() -> tuple[Retailer, ...]:
    return tuple(sorted(RETAILERS, key=lambda retailer: retailer.priority))


def enabled_for_stage(stage: int) -> tuple[Retailer, ...]:
    """הרשתות שנכללות בשלב בנייה מסוים. שלב 1 הוא שופרסל ורמי לוי."""
    limit = 2 if stage <= 1 else len(RETAILERS)
    return in_priority_order()[:limit]
