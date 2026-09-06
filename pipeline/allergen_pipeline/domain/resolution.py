"""הכרעה בין קביעות אלרגן ממקורות שונים.

שני עקרונות מובילים, שניהם מתועדים כהחלטות ארכיטקטורה:

ADR-0002 — מקור שאינו יצרן יכול רק להוסיף אלרגן, לעולם לא לשלול.
לכן קביעה חיובית אחת מספיקה כדי שהאלרגן ייחשב נוכח, גם מול הצהרת
יצרן שאומרת שהוא נעדר. סתירה כזו נרשמת ומוצגת באזהרה אדומה.

ADR-0004 — דירוג האמינות נקבע לכל שדה בנפרד. היצרן גובר על השאלה
אילו אלרגנים קיימים, אבל על השאלה באיזו רמה גוברת קביעה מפורשת
על קביעה שנגזרה מפירוק רשימה שטוחה, גם אם המקור המפורש נמוך יותר.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from . import allergens
from .claims import AllergenClaim, Level, Source, confidence_tier, stricter


@dataclass(frozen=True)
class SourceConflict:
    """שני מקורות שנתנו קביעות מנוגדות לאותו אלרגן."""

    allergen_id: str
    asserted_absent_by: Source
    asserted_present_by: Source
    present_level: Level

    @property
    def message_he(self) -> str:
        allergen = allergens.get(self.allergen_id)
        return (
            f"סתירה בין מקורות לגבי {allergen.label_he}: "
            f"{self.asserted_absent_by.label_he} מצהיר שאינו קיים, "
            f"{self.asserted_present_by.label_he} מצהיר {self.present_level.label_he}. "
            f"המערכת מחמירה ומציגה {self.present_level.label_he}."
        )


@dataclass(frozen=True)
class ResolvedAllergen:
    """המצב המוכרע של אלרגן אחד במוצר אחד."""

    allergen_id: str
    level: Level
    sources: tuple[Source, ...] = ()
    observed_on: date | None = None
    level_inferred: bool = False
    inherited_from: str | None = None

    @property
    def is_known(self) -> bool:
        return self.level is not Level.UNKNOWN


@dataclass(frozen=True)
class ResolvedAllergens:
    """התמונה המלאה של המוצר מול הרשימה הסגורה של האלרגנים."""

    by_allergen: dict[str, ResolvedAllergen]
    conflicts: tuple[SourceConflict, ...] = ()

    def level_of(self, allergen_id: str) -> Level:
        resolved = self.by_allergen.get(allergen_id)
        return resolved.level if resolved else Level.UNKNOWN

    def positives(self) -> tuple[ResolvedAllergen, ...]:
        return tuple(r for r in self.by_allergen.values() if r.level.is_positive)

    def unknown_ids(self) -> frozenset[str]:
        return frozenset(
            allergen_id
            for allergen_id in allergens.all_ids()
            if self.level_of(allergen_id) is Level.UNKNOWN
        )

    @property
    def has_any_data(self) -> bool:
        return any(r.is_known for r in self.by_allergen.values())

    @property
    def latest_observed_on(self) -> date | None:
        dates = [r.observed_on for r in self.by_allergen.values() if r.observed_on]
        return max(dates) if dates else None


@dataclass
class _Accumulator:
    positives: list[AllergenClaim] = field(default_factory=list)
    absences: list[AllergenClaim] = field(default_factory=list)


def _pick_level(positives: list[AllergenClaim]) -> AllergenClaim:
    """בוחר את הקביעה שקובעת את הרמה מבין קביעות חיוביות.

    קביעה מפורשת גוברת על קביעה שנגזרה מפירוק רשימה שטוחה; בין קביעות
    בעלות אותו מעמד גובר המקור האמין יותר; ובין שוות-ערך לגמרי גוברת
    הרמה המחמירה.
    """
    return max(
        positives,
        key=lambda claim: (
            0 if claim.level_inferred else 1,
            confidence_tier(claim.source),
            1 if claim.level is Level.CONTAINS else 0,
            claim.observed_on or date.min,
        ),
    )


def _resolve_one(allergen_id: str, acc: _Accumulator) -> ResolvedAllergen | None:
    if acc.positives:
        deciding = _pick_level(acc.positives)
        contributing = tuple(dict.fromkeys(c.source for c in acc.positives))
        return ResolvedAllergen(
            allergen_id=allergen_id,
            level=deciding.level,
            sources=contributing,
            observed_on=deciding.observed_on,
            level_inferred=deciding.level_inferred,
        )
    if acc.absences:
        latest = max(acc.absences, key=lambda c: c.observed_on or date.min)
        return ResolvedAllergen(
            allergen_id=allergen_id,
            level=Level.ABSENT,
            sources=(latest.source,),
            observed_on=latest.observed_on,
        )
    return None


def _merge_into_parent(
    parent_id: str,
    existing: ResolvedAllergen | None,
    child: ResolvedAllergen,
) -> ResolvedAllergen:
    if existing is None or not existing.level.is_positive:
        return ResolvedAllergen(
            allergen_id=parent_id,
            level=child.level,
            sources=child.sources,
            observed_on=child.observed_on,
            level_inferred=child.level_inferred,
            inherited_from=child.allergen_id,
        )
    merged = stricter(existing.level, child.level)
    if merged is existing.level:
        return existing
    observed = [d for d in (existing.observed_on, child.observed_on) if d]
    return ResolvedAllergen(
        allergen_id=parent_id,
        level=merged,
        sources=tuple(dict.fromkeys(existing.sources + child.sources)),
        observed_on=max(observed) if observed else None,
        level_inferred=child.level_inferred,
        inherited_from=child.allergen_id,
    )


def _inherit_to_parents(
    resolved: dict[str, ResolvedAllergen],
) -> dict[str, ResolvedAllergen]:
    """קשיו שמכיל הופך גם את אגוזי העץ למכיל.

    ההפצה היא כלפי מעלה בלבד. קביעה על אגוזי עץ אינה מלמדת על אף
    תת-סוג מסוים, ולכן אינה יורדת אל הבנים.
    """
    updated = dict(resolved)
    for allergen_id, child in resolved.items():
        if not child.level.is_positive:
            continue
        for parent_id in allergens.ancestors_of(allergen_id):
            updated[parent_id] = _merge_into_parent(
                parent_id, updated.get(parent_id), child
            )
    return updated


def resolve(claims: list[AllergenClaim]) -> ResolvedAllergens:
    """מכריע בין כל הקביעות של מוצר אחד."""
    grouped: dict[str, _Accumulator] = {}
    for claim in claims:
        allergens.get(claim.allergen_id)
        acc = grouped.setdefault(claim.allergen_id, _Accumulator())
        if claim.level.is_positive:
            acc.positives.append(claim)
        elif claim.level is Level.ABSENT:
            acc.absences.append(claim)

    resolved: dict[str, ResolvedAllergen] = {}
    conflicts: list[SourceConflict] = []
    for allergen_id, acc in grouped.items():
        outcome = _resolve_one(allergen_id, acc)
        if outcome is not None:
            resolved[allergen_id] = outcome
        if acc.positives and acc.absences:
            deciding = _pick_level(acc.positives)
            for absent_claim in acc.absences:
                conflicts.append(
                    SourceConflict(
                        allergen_id=allergen_id,
                        asserted_absent_by=absent_claim.source,
                        asserted_present_by=deciding.source,
                        present_level=deciding.level,
                    )
                )

    return ResolvedAllergens(
        by_allergen=_inherit_to_parents(resolved),
        conflicts=tuple(conflicts),
    )
