"""הפיכת מוצר של קמעונאי לקביעות אלרגן.

בניגוד למתאם היצרן, כאן אין פירוק של רשימה שטוחה. הקמעונאי מפרסם שני
שדות מתויגים, ולכן הרמות מפורשות ו-level_inferred נשאר כבוי. זה מה
שמאפשר להן לגבור על רמה שנגזרה מהצהרת יצרן מאוחדת. ראו ADR-0004.
"""

from __future__ import annotations

from datetime import date

from ...domain.claims import AllergenClaim, Level, Source
from ...ingredients.mapping import IngredientAllergenMap
from .shufersal_online import ShufersalProduct


def to_claims(
    product: ShufersalProduct,
    ingredient_map: IngredientAllergenMap,
    observed_on: date,
) -> list[AllergenClaim]:
    """קביעות מפורשות משני השדות, ועוד אלרגנים נסתרים מהרכיבים."""
    contains = _map_terms(product.contains_terms, ingredient_map)
    may_contain = _map_terms(product.may_contain_terms, ingredient_map) - contains

    claims = [
        AllergenClaim(
            allergen_id=allergen_id,
            level=Level.CONTAINS,
            source=Source.RETAILER,
            observed_on=observed_on,
            source_ref=product.page_url,
        )
        for allergen_id in sorted(contains)
    ]
    claims.extend(
        AllergenClaim(
            allergen_id=allergen_id,
            level=Level.MAY_CONTAIN,
            source=Source.RETAILER,
            observed_on=observed_on,
            source_ref=product.page_url,
        )
        for allergen_id in sorted(may_contain)
    )
    claims.extend(
        _hidden_from_ingredients(product, contains | may_contain, ingredient_map, observed_on)
    )
    return claims


def _map_terms(
    terms: tuple[str, ...], ingredient_map: IngredientAllergenMap
) -> set[str]:
    """ממפה מונחים חופשיים לרשימה הסגורה, דרך אותו מנוע התאמה."""
    found: set[str] = set()
    for term in terms:
        found.update(ingredient_map.allergen_ids(term))
    return found


def _hidden_from_ingredients(
    product: ShufersalProduct,
    declared: set[str],
    ingredient_map: IngredientAllergenMap,
    observed_on: date,
) -> list[AllergenClaim]:
    """אלרגן שברשימת הרכיבים ולא בשני שדות ההצהרה.

    גם כאן זו עדות ישירה ולכן הקביעה מפורשת: רכיב שמופיע ברשימה נמצא
    במוצר, בלי קשר לשאלה אם מישהו טרח להצהיר עליו.
    """
    if not product.ingredients_text:
        return []
    from_ingredients = ingredient_map.allergen_ids(product.ingredients_text)
    return [
        AllergenClaim(
            allergen_id=allergen_id,
            level=Level.CONTAINS,
            source=Source.RETAILER,
            observed_on=observed_on,
            source_ref=f"{product.page_url}#ingredients",
        )
        for allergen_id in sorted(from_ingredients - declared)
    ]
