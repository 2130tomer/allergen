"""סינון מוצרים לפי שתי רשימות אלרגנים נפרדות ובלתי תלויות.

הרשימות עצמאיות במכוון: המשתמש בוחר בנפרד אילו אלרגנים להסתיר ברמת
מכיל ואילו ברמת עלול להכיל, בלי מתג גלובלי שמחמיר על הכל. העצמאות
מאפשרת מצב שנראה מוזר אך לגיטימי, שבו אלרגן מסומן ברשימת עלול להכיל
בלבד; במקרה כזה נוצרת אזהרה מפורשת ולא שינוי שקט של הבחירה.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from . import allergens
from .claims import Level
from .resolution import ResolvedAllergens


class Visibility(str, Enum):
    """מה קורה למוצר אחד מול הסינון."""

    VISIBLE = "visible"
    HIDDEN = "hidden"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class SelectionWarning:
    """אזהרה על בחירה שמשאירה פער בטיחותי."""

    allergen_id: str

    @property
    def message_he(self) -> str:
        label = allergens.get(self.allergen_id).label_he
        return (
            f"סימנת {label} רק ברשימת עלול להכיל. "
            f"מוצרים שמכילים {label} עדיין יוצגו."
        )


@dataclass(frozen=True)
class FilterOutcome:
    visibility: Visibility
    matched_allergen_ids: tuple[str, ...] = ()
    unknown_allergen_ids: tuple[str, ...] = ()

    @property
    def is_visible(self) -> bool:
        return self.visibility is Visibility.VISIBLE


@dataclass(frozen=True)
class FilterSelection:
    """מצב הסינון. נשמר מקומית ואינו פרופיל משתמש."""

    contains_exclusions: frozenset[str] = frozenset()
    may_contain_exclusions: frozenset[str] = frozenset()

    def __post_init__(self) -> None:
        for allergen_id in self.contains_exclusions | self.may_contain_exclusions:
            allergens.get(allergen_id)

    @property
    def is_empty(self) -> bool:
        return not (self.contains_exclusions or self.may_contain_exclusions)

    @property
    def selected_ids(self) -> frozenset[str]:
        return self.contains_exclusions | self.may_contain_exclusions

    def warnings(self) -> tuple[SelectionWarning, ...]:
        only_may_contain = self.may_contain_exclusions - self.contains_exclusions
        return tuple(
            SelectionWarning(allergen_id) for allergen_id in sorted(only_may_contain)
        )

    def _expanded_contains(self) -> set[str]:
        return allergens.expand_selection(set(self.contains_exclusions))

    def _expanded_may_contain(self) -> set[str]:
        return allergens.expand_selection(set(self.may_contain_exclusions))

    def apply(self, resolved: ResolvedAllergens) -> FilterOutcome:
        """מכריע אם מוצר מוצג, מוסתר, או נופל לסעיף אין מידע."""
        if self.is_empty:
            return FilterOutcome(Visibility.VISIBLE)

        matched: list[str] = []
        for allergen_id in sorted(self._expanded_contains()):
            if resolved.level_of(allergen_id) is Level.CONTAINS:
                matched.append(allergen_id)
        for allergen_id in sorted(self._expanded_may_contain()):
            if resolved.level_of(allergen_id) is Level.MAY_CONTAIN:
                matched.append(allergen_id)

        if matched:
            return FilterOutcome(
                Visibility.HIDDEN, matched_allergen_ids=tuple(dict.fromkeys(matched))
            )

        unknown = tuple(
            allergen_id
            for allergen_id in sorted(self.selected_ids)
            if not _selection_is_known(resolved, allergen_id)
        )
        if unknown:
            return FilterOutcome(Visibility.UNKNOWN, unknown_allergen_ids=unknown)

        return FilterOutcome(Visibility.VISIBLE)


def _selection_is_known(resolved: ResolvedAllergens, allergen_id: str) -> bool:
    """האם יש לנו מידע כלשהו על האלרגן שנבחר, או על אחד מתת-סוגיו."""
    if resolved.level_of(allergen_id) is not Level.UNKNOWN:
        return True
    return any(
        resolved.level_of(subtype_id) is not Level.UNKNOWN
        for subtype_id in allergens.subtypes_of(allergen_id)
    )


@dataclass
class FilteredList:
    """תוצאת סינון של רשימת מוצרים, מופרדת לשתי קבוצות תצוגה."""

    visible: list[str] = field(default_factory=list)
    unknown: list[str] = field(default_factory=list)
    hidden_count: int = 0

    @property
    def total_shown(self) -> int:
        return len(self.visible) + len(self.unknown)


def partition(
    selection: FilterSelection,
    products: list[tuple[str, ResolvedAllergens]],
) -> FilteredList:
    """מחלק מוצרים לרשימה המוצגת, לסעיף אין מידע, ולמה שהוסתר.

    מוצרי אין מידע אינם מעורבבים ברשימה הראשית ואינם נעלמים בשקט.
    """
    result = FilteredList()
    for barcode, resolved in products:
        outcome = selection.apply(resolved)
        if outcome.visibility is Visibility.VISIBLE:
            result.visible.append(barcode)
        elif outcome.visibility is Visibility.UNKNOWN:
            result.unknown.append(barcode)
        else:
            result.hidden_count += 1
    return result
