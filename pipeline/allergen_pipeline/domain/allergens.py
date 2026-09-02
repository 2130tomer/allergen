"""הרשימה הסגורה של האלרגנים בני-הדיווח, והיררכיית אגוזי העץ.

הרשימה נגזרת מתקנות סימון מזון ארוז מראש בישראל. אגוזי עץ מפוצלים
לתת-סוגים, כי אלרגיה לקשיו בלבד היא נפוצה וסינון כל אגוזי העץ בגללה
הופך את האפליקציה לחסרת ערך. סינון של אגוז-אב תופס את כל בניו.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator

TREE_NUTS_ID = "tree_nuts"


@dataclass(frozen=True)
class Allergen:
    id: str
    label_he: str
    parent_id: str | None = None

    @property
    def is_subtype(self) -> bool:
        return self.parent_id is not None


_ALLERGEN_LIST: tuple[Allergen, ...] = (
    Allergen("gluten", "גלוטן"),
    Allergen("milk", "חלב"),
    Allergen("eggs", "ביצים"),
    Allergen("peanuts", "בוטנים"),
    Allergen("soy", "סויה"),
    Allergen("sesame", "שומשום"),
    Allergen("fish", "דגים"),
    Allergen("crustaceans", "סרטנים"),
    Allergen("molluscs", "רכיכות"),
    Allergen(TREE_NUTS_ID, "אגוזי עץ"),
    Allergen("almond", "שקד", TREE_NUTS_ID),
    Allergen("walnut", "אגוז מלך", TREE_NUTS_ID),
    Allergen("cashew", "קשיו", TREE_NUTS_ID),
    Allergen("pecan", "פקאן", TREE_NUTS_ID),
    Allergen("pistachio", "פיסטוק", TREE_NUTS_ID),
    Allergen("hazelnut", "אגוז לוז", TREE_NUTS_ID),
    Allergen("macadamia", "מקדמיה", TREE_NUTS_ID),
    Allergen("brazil_nut", "אגוז ברזיל", TREE_NUTS_ID),
    Allergen("mustard", "חרדל"),
    Allergen("celery", "סלרי"),
    Allergen("lupin", "לופין"),
    Allergen("sulphites", "סולפיטים"),
)

ALLERGENS: dict[str, Allergen] = {a.id: a for a in _ALLERGEN_LIST}


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


def expand_selection(selected_ids: set[str]) -> set[str]:
    """בחירת אגוז-אב תופסת את כל בניו.

    בחירת "אגוזי עץ" בסינון חייבת להסתיר גם מוצר שמסומן "קשיו" בלבד.
    """
    expanded = set(selected_ids)
    for allergen_id in selected_ids:
        expanded.update(subtypes_of(allergen_id))
    return expanded


def iter_allergens() -> Iterator[Allergen]:
    return iter(_ALLERGEN_LIST)
