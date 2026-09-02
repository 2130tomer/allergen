"""מיפוי רכיבים לאלרגנים, ובעיקר: מה אסור שיזוהה בטעות.

אזעקת שווא כאן היא לא אי-נוחות. היא מסתירה מוצר תקין, ואם היא קורית
מספיק פעמים המשתמש מפסיק להאמין לסינון ומפסיק להשתמש בו.
"""

from __future__ import annotations

import pytest

from allergen_pipeline.ingredients.mapping import IngredientAllergenMap

BAMBA_INGREDIENTS = "בוטנים טחונים (54%), גריסי תירס, שמן חמניות, מלח, ברזל, ויטמינים"


@pytest.fixture(scope="module")
def ingredient_map() -> IngredientAllergenMap:
    return IngredientAllergenMap.load()


class TestPositiveDetection:
    def test_bamba_ingredients_yield_peanuts(self, ingredient_map):
        assert ingredient_map.allergen_ids(BAMBA_INGREDIENTS) == {"peanuts"}

    def test_soy_lecithin_is_detected(self, ingredient_map):
        assert "soy" in ingredient_map.allergen_ids("סוכר, לציטין סויה, וניל")

    def test_lecithin_in_parentheses_is_detected(self, ingredient_map):
        # הסוגריים נעלמים בנרמול, ולכן "לציטין (סויה)" מתנהג כמו "לציטין סויה".
        assert "soy" in ingredient_map.allergen_ids("שוקולד, לציטין (סויה)")

    def test_casein_is_milk(self, ingredient_map):
        assert "milk" in ingredient_map.allergen_ids("נתרן קזאינט, מלח")

    def test_tahini_is_sesame(self, ingredient_map):
        assert "sesame" in ingredient_map.allergen_ids("טחינה גולמית, מים")

    def test_a_prefixed_word_still_matches(self, ingredient_map):
        assert "milk" in ingredient_map.allergen_ids("מוצר המכיל אבקת חלב")

    def test_cashew_maps_to_its_own_subtype(self, ingredient_map):
        assert "cashew" in ingredient_map.allergen_ids("אגוזי קשיו קלויים")

    def test_several_allergens_in_one_list(self, ingredient_map):
        found = ingredient_map.allergen_ids("קמח חיטה, חמאה, ביצים, שקדים")
        assert {"gluten", "milk", "eggs", "almond"} <= found


class TestFalsePositives:
    def test_protein_is_not_milk(self, ingredient_map):
        # "חלבון" מכיל את האותיות של "חלב" ואינו מעיד עליו.
        assert "milk" not in ingredient_map.allergen_ids("חלבון אפונה, מים")

    def test_coconut_milk_is_not_milk(self, ingredient_map):
        assert "milk" not in ingredient_map.allergen_ids("חלב קוקוס, סוכר")

    def test_soy_milk_is_soy_not_milk(self, ingredient_map):
        found = ingredient_map.allergen_ids("חלב סויה")
        assert "milk" not in found

    def test_cocoa_butter_is_not_milk(self, ingredient_map):
        assert "milk" not in ingredient_map.allergen_ids("מסת קקאו, חמאת קקאו")

    def test_peanut_butter_is_peanuts_and_not_milk(self, ingredient_map):
        found = ingredient_map.allergen_ids("חמאת בוטנים, מלח")
        assert "peanuts" in found
        assert "milk" not in found

    def test_corn_flour_is_not_gluten(self, ingredient_map):
        assert "gluten" not in ingredient_map.allergen_ids("קמח תירס, מים")

    def test_buckwheat_is_not_gluten(self, ingredient_map):
        assert "gluten" not in ingredient_map.allergen_ids("כוסמת, מים")

    def test_nutmeg_is_not_a_tree_nut(self, ingredient_map):
        found = ingredient_map.allergen_ids("אגוז מוסקט, קינמון")
        assert "tree_nuts" not in found

    def test_empty_text_finds_nothing(self, ingredient_map):
        assert ingredient_map.allergen_ids(None) == set()
        assert ingredient_map.allergen_ids("") == set()


class TestExplainability:
    def test_a_match_reports_the_phrase_that_caused_it(self, ingredient_map):
        matches = ingredient_map.match("סוכר, לציטין סויה")
        soy = next(m for m in matches if m.allergen_id == "soy")
        assert "סויה" in soy.matched_phrase
        assert "סויה" in soy.explanation_he

    def test_matches_come_back_in_reading_order(self, ingredient_map):
        matches = ingredient_map.match("קמח חיטה, חמאה")
        assert [m.allergen_id for m in matches] == ["gluten", "milk"]

    def test_a_longer_phrase_wins_over_a_shorter_one(self, ingredient_map):
        matches = ingredient_map.match("אגוז מלך")
        assert [m.allergen_id for m in matches] == ["walnut"]


class TestMapIntegrity:
    def test_every_key_is_a_known_allergen(self):
        # הבנאי מאמת מול הרשימה הסגורה; טעינה שמצליחה היא ההוכחה.
        assert IngredientAllergenMap.load() is not None

    def test_an_unknown_allergen_key_is_rejected(self):
        from allergen_pipeline.domain.allergens import UnknownAllergenError

        with pytest.raises(UnknownAllergenError):
            IngredientAllergenMap(allergen_terms={"unicorn": ["חדקרן"]})
