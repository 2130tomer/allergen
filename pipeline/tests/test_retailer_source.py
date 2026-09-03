"""מתאם שופרסל אונליין: המקור היחיד שמפריד במפורש בין הרמות.

המקבע כאן הוא מבנה אמיתי מה-API, כולל שתי נקודות שקל לטעות בהן: שם
השדה של "מכיל" ושל "עלול להכיל" זהה, וההבחנה ביניהם היא בקוד בלבד.
"""

from __future__ import annotations

from datetime import date

import pytest

from allergen_pipeline.domain.claims import Level, Source, confidence_tier
from allergen_pipeline.domain.resolution import resolve
from allergen_pipeline.ingredients.mapping import IngredientAllergenMap
from allergen_pipeline.sources.retailers import claims as retailer_claims
from allergen_pipeline.sources.retailers import shufersal_online

TODAY = date(2026, 9, 3)
BARCODE = "7290100680728"

# מבנה אמיתי מהתשובה של /online/he/products/P_7290100680728.
# שים לב: שני שדות האלרגנים נושאים את אותו name, ורק ה-code מבחין.
API_PAYLOAD = {
    "code": f"P_{BARCODE}",
    "sku": BARCODE,
    "name": "פירורית אסם",
    "brandName": "אסם",
    "food": True,
    "ean": None,
    "classifications": [
        {
            "features": [
                {
                    "code": "miglogClassificationSystem/1.0/125.125_125",
                    "name": "אלרגנים",
                    "featureValues": [{"value": "גלוטן חיטה"}],
                },
                {
                    "code": "miglogClassificationSystem/1.0/126.126_126",
                    "name": "אלרגנים",
                    "featureValues": [
                        {"value": "סויה"},
                        {"value": "סלרי"},
                        {"value": "שומשום"},
                    ],
                },
                {
                    "code": "miglogClassificationSystem/1.0/110.1_110",
                    "name": "רכיבים",
                    "featureValues": [
                        {"value": "קמח חיטה (מכיל גלוטן), מלח, שמרים"}
                    ],
                },
                {
                    "code": "miglogClassificationSystem/1.0/111.201_111",
                    "name": "אנרגיה",
                    "featureValues": [{"value": "369"}],
                },
            ]
        }
    ],
}


@pytest.fixture(scope="module")
def ingredient_map() -> IngredientAllergenMap:
    return IngredientAllergenMap.load()


class TestParsing:
    def product(self):
        return shufersal_online.parse_product_json(API_PAYLOAD, BARCODE)

    def test_the_barcode_comes_from_the_sku_field(self):
        assert self.product().barcode == BARCODE

    def test_contains_and_may_contain_are_separated_by_code(self):
        product = self.product()
        assert "גלוטן חיטה" in product.contains_terms
        assert "סויה" in product.may_contain_terms
        assert "סויה" not in product.contains_terms

    def test_the_ingredient_text_is_read(self):
        assert "קמח חיטה" in (self.product().ingredients_text or "")

    def test_nutrition_values_do_not_leak_into_allergens(self):
        product = self.product()
        assert "369" not in product.contains_terms
        assert "369" not in product.may_contain_terms

    def test_the_food_flag_is_read(self):
        assert self.product().is_food is True

    def test_a_mismatched_sku_is_rejected(self):
        """שיוך אלרגנים לברקוד שגוי הוא בדיוק הטעות שאסור לעשות."""
        payload = {**API_PAYLOAD, "sku": "7290000000001"}
        assert shufersal_online.parse_product_json(payload, BARCODE) is None

    def test_a_payload_without_sku_is_rejected(self):
        payload = {key: value for key, value in API_PAYLOAD.items() if key != "sku"}
        assert shufersal_online.parse_product_json(payload, BARCODE) is None


class TestClaims:
    def claims(self, ingredient_map):
        product = shufersal_online.parse_product_json(API_PAYLOAD, BARCODE)
        return retailer_claims.to_claims(product, ingredient_map, TODAY)

    def test_levels_match_the_two_fields(self, ingredient_map):
        levels = {c.allergen_id: c.level for c in self.claims(ingredient_map)}
        assert levels["gluten"] is Level.CONTAINS
        assert levels["soy"] is Level.MAY_CONTAIN
        assert levels["sesame"] is Level.MAY_CONTAIN
        assert levels["celery"] is Level.MAY_CONTAIN

    def test_claims_are_explicit_not_inferred(self, ingredient_map):
        """זה מה שמאפשר להן לגבור על רמה שנגזרה מרשימה שטוחה של יצרן."""
        assert all(not c.level_inferred for c in self.claims(ingredient_map))

    def test_the_source_is_the_retailer(self, ingredient_map):
        assert all(c.source is Source.RETAILER for c in self.claims(ingredient_map))

    def test_an_allergen_in_both_fields_stays_contains(self, ingredient_map):
        payload = {
            "sku": BARCODE,
            "classifications": [
                {
                    "features": [
                        {
                            "code": ".../125.125_125",
                            "featureValues": [{"value": "סויה"}],
                        },
                        {
                            "code": ".../126.126_126",
                            "featureValues": [{"value": "סויה"}],
                        },
                    ]
                }
            ],
        }
        product = shufersal_online.parse_product_json(payload, BARCODE)
        found = retailer_claims.to_claims(product, ingredient_map, TODAY)
        soy = [c for c in found if c.allergen_id == "soy"]
        assert len(soy) == 1
        assert soy[0].level is Level.CONTAINS


class TestPrecedence:
    def test_the_retailer_outranks_open_food_facts(self):
        assert confidence_tier(Source.RETAILER) > confidence_tier(
            Source.OPEN_FOOD_FACTS
        )

    def test_the_manufacturer_still_outranks_the_retailer(self):
        assert confidence_tier(Source.MANUFACTURER) > confidence_tier(Source.RETAILER)

    def test_a_retailer_may_not_assert_absence(self):
        """הקמעונאי מעתיק תווית ואינו האחראי עליה. ראו ADR-0002."""
        assert not Source.RETAILER.may_assert_absence

    def test_explicit_retailer_level_beats_inferred_manufacturer_level(
        self, ingredient_map
    ):
        """המקרה המרכזי של ADR-0004, עכשיו עם שני מקורות אמיתיים.

        אסם מפרסמת רשימה שטוחה שממנה נגזר "מכיל סויה"; שופרסל מפרסמת
        במפורש "עלול להכיל סויה". המפורש מנצח.
        """
        from allergen_pipeline.domain.claims import AllergenClaim

        inferred = AllergenClaim(
            allergen_id="soy",
            level=Level.CONTAINS,
            source=Source.MANUFACTURER,
            observed_on=TODAY,
            level_inferred=True,
        )
        explicit = AllergenClaim(
            allergen_id="soy",
            level=Level.MAY_CONTAIN,
            source=Source.RETAILER,
            observed_on=TODAY,
        )
        assert resolve([inferred, explicit]).level_of("soy") is Level.MAY_CONTAIN


class TestTermSplitting:
    def test_a_multi_word_term_is_kept_whole_and_split(self):
        terms = shufersal_online.split_terms(["גלוטן חיטה"])
        assert "גלוטן חיטה" in terms
        assert "גלוטן" in terms

    def test_comma_separated_values_become_separate_terms(self):
        terms = shufersal_online.split_terms(["סויה, סלרי, שומשום"])
        assert {"סויה", "סלרי", "שומשום"} <= set(terms)

    def test_empty_values_yield_nothing(self):
        assert shufersal_online.split_terms([]) == ()
        assert shufersal_online.split_terms(["  "]) == ()
