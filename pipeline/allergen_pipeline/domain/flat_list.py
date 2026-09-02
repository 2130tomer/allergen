"""פירוק רשימת אלרגנים שטוחה של יצרן לרמות. ראו ADR-0004.

אתרי יצרנים מפרסמים לרוב רשימה אחת בלי להבחין בין מכיל לעלול להכיל.
דף במבה קלאסית של אסם מציג "בוטנים סויה" בשורה אחת, בזמן שהמוצר מכיל
בוטנים ורק עלול להכיל סויה. ההבחנה משוחזרת בהצלבה מול רשימת הרכיבים.
"""

from __future__ import annotations

from datetime import date

from .claims import AllergenClaim, Level, Source


def decompose(
    flat_allergen_ids: list[str],
    allergens_in_ingredients: set[str] | None,
    source: Source,
    observed_on: date,
    source_ref: str | None = None,
) -> list[AllergenClaim]:
    """הופך רשימה שטוחה לקביעות עם רמה.

    allergens_in_ingredients הוא אוסף האלרגנים שזוהו ברשימת הרכיבים של
    המוצר, או None כשאין רשימת רכיבים בכלל.

    האלרגן מופיע ברכיבים ⟵ מכיל.
    האלרגן אינו מופיע ברכיבים ⟵ עלול להכיל.
    אין רשימת רכיבים ⟵ מכיל, הכיוון המחמיר.

    כל קביעה שנוצרת כאן מסומנת level_inferred כדי שקביעה מפורשת ממקור
    אחר תוכל לגבור עליה בשאלת הרמה.
    """
    has_ingredients = allergens_in_ingredients is not None
    found = allergens_in_ingredients or set()

    claims: list[AllergenClaim] = []
    for allergen_id in dict.fromkeys(flat_allergen_ids):
        if not has_ingredients or allergen_id in found:
            level = Level.CONTAINS
        else:
            level = Level.MAY_CONTAIN
        claims.append(
            AllergenClaim(
                allergen_id=allergen_id,
                level=level,
                source=source,
                observed_on=observed_on,
                source_ref=source_ref,
                level_inferred=True,
            )
        )
    return claims


def hidden_allergen_claims(
    allergens_in_ingredients: set[str],
    declared_allergen_ids: set[str],
    source: Source,
    observed_on: date,
    source_ref: str | None = None,
) -> list[AllergenClaim]:
    """אלרגנים שנמצאו ברכיבים אך לא הופיעו בהצהרת היצרן.

    זה המקרה של לציטין סויה שהיצרן שכח להזכיר. הקביעה מפורשת ולא נגזרת,
    כי רכיב ברשימת הרכיבים הוא עדות ישירה למכיל.
    """
    return [
        AllergenClaim(
            allergen_id=allergen_id,
            level=Level.CONTAINS,
            source=source,
            observed_on=observed_on,
            source_ref=source_ref,
        )
        for allergen_id in sorted(allergens_in_ingredients - declared_allergen_ids)
    ]
