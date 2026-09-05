"""הצהרות "ללא": מתי מותר לצבוע מוצר כנקי, ובעיקר מתי אסור.

זהו המקום היחיד באפליקציה שבו נאמר על מוצר שאינו מכיל אלרגן, ולכן
הבדיקות כאן נוטות במכוון לכיוון השלילי: רובן מוודאות שהצהרה *לא*
מזוהה, ולא שהיא כן.
"""

from __future__ import annotations

import pytest

from allergen_pipeline.ingredients.free_from import FreeFromDetector


@pytest.fixture(scope="module")
def detector() -> FreeFromDetector:
    return FreeFromDetector.load()


def free_from_ids(detector: FreeFromDetector, text: str) -> set[str]:
    claims, _ = detector.detect(text)
    return {claim.allergen_id for claim in claims}


def reduced_ids(detector: FreeFromDetector, text: str) -> set[str]:
    _, claims = detector.detect(text)
    return {claim.allergen_id for claim in claims}


class TestExplicitDeclaration:
    def test_a_gluten_free_declaration_is_recognised(self, detector):
        assert "gluten" in free_from_ids(detector, "לחם ללא גלוטן 500 גרם")

    def test_the_natul_wording_is_recognised_too(self, detector):
        assert "lactose" in free_from_ids(detector, "חלב נטול לקטוז 1 ליטר")

    def test_english_wording_on_the_package_is_recognised(self, detector):
        assert "gluten" in free_from_ids(detector, "Rice cakes gluten free")

    def test_a_product_with_no_declaration_yields_nothing(self, detector):
        assert free_from_ids(detector, "ביסלי גריל 70 גרם") == set()


class TestReducedIsNotFree:
    """ההבחנה המסוכנת ביותר במודול. ראו את תיעוד free_from.py."""

    def test_low_lactose_is_not_a_free_from_declaration(self, detector):
        assert "lactose" not in free_from_ids(detector, "חלב תנובה דל לקטוז 3%")

    def test_low_lactose_is_recorded_as_reduced(self, detector):
        assert "lactose" in reduced_ids(detector, "חלב תנובה דל לקטוז 3%")

    def test_reduced_wins_over_free_for_the_same_allergen(self, detector):
        """'דל לקטוז' מכיל את האסימון 'לקטוז'; המחמיר חייב לנצח."""
        text = "משקה דל לקטוז ללא לקטוז מוסף"
        assert "lactose" not in free_from_ids(detector, text)

    def test_a_reduction_does_not_mask_a_real_declaration_elsewhere(self, detector):
        text = "יוגורט דל לקטוז ללא גלוטן"
        assert free_from_ids(detector, text) == {"gluten"}
        assert reduced_ids(detector, text) == {"lactose"}


class TestClaimsThatMustNotCount:
    def test_parve_is_a_kashrut_mark_and_not_an_allergen_claim(self, detector):
        assert free_from_ids(detector, "עוגיות פרווה") == set()

    def test_vegan_is_not_a_free_from_declaration(self, detector):
        """טבעוני מעיד על מדיניות רכיבים, לא על בקרת עקבות בפס הייצור."""
        assert free_from_ids(detector, "שוקולד טבעוני 100 גרם") == set()

    def test_sugar_free_does_not_clear_any_allergen(self, detector):
        assert free_from_ids(detector, "משקה ללא סוכר") == set()

    def test_empty_input_is_safe(self, detector):
        assert detector.detect(None) == ([], [])
        assert detector.detect("") == ([], [])
        assert detector.detect("   ") == ([], [])


class TestDeclarationIsScopedToTheAllergenNamed:
    def test_a_milk_declaration_does_not_clear_nuts(self, detector):
        ids = free_from_ids(detector, "משקה שקדים ללא חלב")
        assert ids == {"milk"}

    def test_several_declarations_are_all_captured(self, detector):
        ids = free_from_ids(detector, "חטיף ללא גלוטן ללא בוטנים")
        assert ids == {"gluten", "peanuts"}
