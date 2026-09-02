"""חוזה משותף למתאמי אתרי יצרנים.

אתרי היצרנים הם המקור האמין ביותר לשאלה אילו אלרגנים קיימים במוצר,
אך רובם מפרסמים רשימה שטוחה בלי רמות. ראו ADR-0004. לכן מתאם יצרן
מחזיר את מה שראה בפועל, והפירוק לרמות נעשה בשלב מאוחר יותר.

כלל ברזל: מוצר שלא הצלחנו לקשר לברקוד בוודאות אינו מקבל שיוך אלרגנים
כלל. התאמה שגויה כאן היא בדיוק סוג הטעות שהאפליקציה אמורה למנוע.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from ...domain import flat_list
from ...domain.claims import AllergenClaim, Source
from ...ingredients.mapping import IngredientAllergenMap


@dataclass(frozen=True)
class ManufacturerProduct:
    """מוצר כפי שנקרא מדף באתר יצרן."""

    manufacturer_id: str
    manufacturer_name: str
    page_url: str
    product_name: str | None = None
    barcode: str | None = None
    image_url: str | None = None
    ingredients_text: str | None = None
    # הרשימה כפי שהופיעה בדף, לפני מיפוי לרשימה הסגורה ולפני פירוק לרמות.
    raw_allergen_terms: tuple[str, ...] = ()

    @property
    def is_linkable(self) -> bool:
        return bool(self.barcode)


def to_claims(
    product: ManufacturerProduct,
    ingredient_map: IngredientAllergenMap,
    observed_on: date,
) -> list[AllergenClaim]:
    """הופך מוצר של יצרן לקביעות אלרגן.

    שני חלקים: פירוק הרשימה השטוחה שהיצרן הצהיר עליה, ובנוסף אלרגנים
    שנמצאו ברכיבים אך נעדרו מההצהרה. השני הוא המקרה של לציטין סויה
    שהיצרן שכח להזכיר.
    """
    if not product.is_linkable:
        return []

    from_ingredients = ingredient_map.allergen_ids(product.ingredients_text)
    has_ingredients = bool(product.ingredients_text)
    declared = _map_declared_terms(product.raw_allergen_terms, ingredient_map)

    claims = flat_list.decompose(
        flat_allergen_ids=sorted(declared),
        allergens_in_ingredients=from_ingredients if has_ingredients else None,
        source=Source.MANUFACTURER,
        observed_on=observed_on,
        source_ref=product.page_url,
    )
    claims.extend(
        flat_list.hidden_allergen_claims(
            allergens_in_ingredients=from_ingredients,
            declared_allergen_ids=declared,
            source=Source.MANUFACTURER,
            observed_on=observed_on,
            source_ref=product.page_url,
        )
    )
    return claims


def _map_declared_terms(
    terms: tuple[str, ...],
    ingredient_map: IngredientAllergenMap,
) -> set[str]:
    """ממפה את מילות ההצהרה של היצרן לרשימה הסגורה.

    ההצהרה נכתבת בשפה חופשית, ולכן היא עוברת דרך אותו מנוע התאמה
    שמשמש לרכיבים.
    """
    declared: set[str] = set()
    for term in terms:
        declared.update(ingredient_map.allergen_ids(term))
    return declared
