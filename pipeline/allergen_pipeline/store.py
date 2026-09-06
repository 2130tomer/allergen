"""מדיניות המיזוג של קביעות אלרגן לאורך ריצות.

הכלל שמנחה את כל הקובץ הזה: **כישלון או שתיקה של מקור לעולם אינם
מחזירים מוצר למצב אין מידע**. מוצר שהיה ידוע כמכיל בוטנים ופתאום
המקור מפסיק לדווח עליו הוא כמעט תמיד תקלה אצלנו, לא שינוי במוצר.
לכן הקביעה האחרונה התקינה נשמרת עם התאריך שלה, והפער מסומן לבדיקה.

שינוי אמיתי במוצר מזוהה אחרת: כשטקסט הרכיבים משתנה, הקביעות הישנות
מאותו מקור מפסיקות להיות רלוונטיות ומוחלפות.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from .domain.claims import AllergenClaim, Source
from .text import hebrew


@dataclass
class MergeOutcome:
    claims: list[AllergenClaim] = field(default_factory=list)
    kept_stale_sources: tuple[Source, ...] = ()
    retired_sources: tuple[Source, ...] = ()
    needs_review: bool = False
    review_reason: str | None = None


@dataclass
class ProductClaims:
    """כל הקביעות הידועות על מוצר אחד, לכל המקורות."""

    barcode: str
    claims: list[AllergenClaim] = field(default_factory=list)
    ingredients_fingerprint: str | None = None

    def by_source(self, source: Source) -> list[AllergenClaim]:
        return [claim for claim in self.claims if claim.source is source]

    def without_source(self, source: Source) -> list[AllergenClaim]:
        return [claim for claim in self.claims if claim.source is not source]


def fingerprint_ingredients(text: str | None) -> str | None:
    """טביעת אצבע של רשימת הרכיבים, לזיהוי שינוי מתכון.

    מבוססת על הטקסט המנורמל, כדי ששינוי כתיב או פיסוק לא ייחשב לשינוי
    מתכון ולא יפסיל קביעות תקינות.
    """
    if not text:
        return None
    normalized = hebrew.normalize(text)
    return normalized or None


def merge_source_claims(
    existing: ProductClaims,
    source: Source,
    incoming: list[AllergenClaim],
    run_accepted: bool,
    incoming_ingredients: str | None = None,
) -> MergeOutcome:
    """ממזג את תוצאות מקור אחד לתוך הקביעות הקיימות של מוצר."""
    previous_from_source = existing.by_source(source)

    if not run_accepted:
        return MergeOutcome(
            claims=list(existing.claims),
            kept_stale_sources=(source,) if previous_from_source else (),
        )

    if not incoming:
        if not previous_from_source:
            return MergeOutcome(claims=list(existing.claims))
        # המקור הפסיק לדווח. שומרים את הידוע האחרון ומסמנים לבדיקה.
        return MergeOutcome(
            claims=list(existing.claims),
            kept_stale_sources=(source,),
            needs_review=True,
            review_reason=(
                f"{source.label_he} הפסיק לדווח אלרגנים על "
                f"{existing.barcode}. המידע הקודם נשמר ולא הוסר."
            ),
        )

    incoming_fingerprint = fingerprint_ingredients(incoming_ingredients)
    reformulated = (
        incoming_fingerprint is not None
        and existing.ingredients_fingerprint is not None
        and incoming_fingerprint != existing.ingredients_fingerprint
    )

    merged = existing.without_source(source) + list(incoming)
    return MergeOutcome(
        claims=merged,
        retired_sources=(source,) if previous_from_source else (),
        needs_review=reformulated,
        review_reason=(
            f"רשימת הרכיבים של {existing.barcode} השתנתה. "
            "הקביעות הישנות מאותו מקור הוחלפו."
        )
        if reformulated
        else None,
    )


def drop_claims_without_barcode(
    claims: list[AllergenClaim], barcode: str | None
) -> list[AllergenClaim]:
    """כלל הברזל של הקישור: אין ברקוד ודאי, אין שיוך אלרגנים."""
    return list(claims) if barcode else []


def latest_observation(claims: list[AllergenClaim]) -> date | None:
    return max((claim.observed_on for claim in claims if claim.observed_on is not None), default=None)
