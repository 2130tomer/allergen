"""הפיכת מוצר של קמעונאי לקביעות אלרגן.

בניגוד למתאם היצרן, כאן אין פירוק של רשימה שטוחה. הקמעונאי מפרסם שני
שדות מתויגים, ולכן הרמות מפורשות ו-level_inferred נשאר כבוי. זה מה
שמאפשר להן לגבור על רמה שנגזרה מהצהרת יצרן מאוחדת. ראו ADR-0004.
"""

from __future__ import annotations

from datetime import date

from ...domain.claims import AllergenClaim, Level, Source
from ...ingredients.free_from import FreeFromDetector
from ...ingredients.mapping import IngredientAllergenMap
from .rami_levy_online import RamiLevyProduct
from .shufersal_online import ShufersalProduct


def to_claims(
    product: ShufersalProduct,
    ingredient_map: IngredientAllergenMap,
    observed_on: date,
    free_from: FreeFromDetector | None = None,
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
    if free_from is not None:
        claims.extend(_declared_claims(product, free_from, observed_on))
    return claims


def rami_levy_to_claims(
    product: RamiLevyProduct,
    ingredient_map: IngredientAllergenMap,
    observed_on: date,
    free_from: FreeFromDetector | None = None,
) -> list[AllergenClaim]:
    """קביעות ממוצר של רמי לוי.

    כאן האלרגנים כבר מפוענחים מקודים לרשימה הסגורה, ולכן אין מיפוי
    מונחים. הרמה מגיעה מהשדה שבו הקוד הופיע, ולכן level_inferred כבוי
    בדיוק כמו אצל שופרסל.

    שים לב שקוד שאינו במילון אינו הופך לשום קביעה, וגם אינו הופך את
    המוצר לנקי: הוא נספר ב-unknown_codes ומדווח. היעדר פענוח הוא היעדר
    מידע, לא היעדר אלרגן.
    """
    contains = set(product.contains_ids)
    may_contain = set(product.may_contain_ids) - contains

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

    if product.ingredients_text:
        from_ingredients = ingredient_map.allergen_ids(product.ingredients_text)
        claims.extend(
            AllergenClaim(
                allergen_id=allergen_id,
                level=Level.CONTAINS,
                source=Source.RETAILER,
                observed_on=observed_on,
                source_ref=f"{product.page_url}#ingredients",
            )
            for allergen_id in sorted(from_ingredients - contains - may_contain)
        )

    if free_from is not None:
        declared, reduced = free_from.detect(product.name, product.ingredients_text)
        claims.extend(
            AllergenClaim(
                allergen_id=claim.allergen_id,
                level=Level.ABSENT,
                source=Source.DECLARED_FREE_FROM,
                observed_on=observed_on,
                source_ref=product.page_url,
            )
            for claim in declared
        )
        claims.extend(
            AllergenClaim(
                allergen_id=claim.allergen_id,
                level=Level.CONTAINS,
                source=Source.DECLARED_FREE_FROM,
                observed_on=observed_on,
                source_ref=product.page_url,
            )
            for claim in reduced
        )
    return claims


def _declared_claims(
    product: ShufersalProduct,
    free_from: FreeFromDetector,
    observed_on: date,
) -> list[AllergenClaim]:
    """הצהרות "ללא" ו"דל" שמופיעות על האריזה.

    ההצהרות נקראות משם המוצר ומטקסט התווית. הן אינן מתנגשות כאן עם
    קביעות אחרות ואינן מבטלות אותן: סתירה בין הצהרת "ללא חלב" לבין
    אבקת חלב ברשימת הרכיבים היא ממצא שיש להציג למשתמש, לא ממצא
    שמכריעים בשקט. ההכרעה והסימון שייכים ל-domain.resolution.

    הצהרת הפחתה נרשמת כנוכחות. מוצר דל לקטוז מכיל לקטוז.
    """
    declared, reduced = free_from.detect(product.name, product.ingredients_text)
    claims = [
        AllergenClaim(
            allergen_id=claim.allergen_id,
            level=Level.ABSENT,
            source=Source.DECLARED_FREE_FROM,
            observed_on=observed_on,
            source_ref=product.page_url,
        )
        for claim in declared
    ]
    claims.extend(
        AllergenClaim(
            allergen_id=claim.allergen_id,
            level=Level.CONTAINS,
            source=Source.DECLARED_FREE_FROM,
            observed_on=observed_on,
            source_ref=product.page_url,
        )
        for claim in reduced
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
