"""מתאם רמי לוי, ובעיקר המלכודות שהמילון חשף.

הבדיקות כאן מקבעות שגיאות שהיו קורות אילו הקודים פוענחו בניחוש. שתי
החשובות הן 6843 ו-6942: הראשון אומר "אין" והשני "לא מצוין על גבי
התוית". קורלציה סטטיסטית ייחסה את 6843 לאגוזי קשיו, וניחוש כזה היה
מייצר אלרגן על מוצר שהוצהר עליו שאין לו.
"""

from __future__ import annotations

from datetime import date

from allergen_pipeline.domain.claims import Level, Source
from allergen_pipeline.ingredients.mapping import IngredientAllergenMap
from allergen_pipeline.sources.retailers import rami_levy_online as rami
from allergen_pipeline.sources.retailers.claims import rami_levy_to_claims

TODAY = date(2026, 9, 5)
BAMBA = "7290000066318"


def payload(barcode=BAMBA, contains=None, may_contain=None, ingredients=None, name="במבה"):
    gs = {}
    if contains is not None:
        gs[rami.CONTAINS_FIELD] = contains
    if may_contain is not None:
        gs[rami.MAY_CONTAIN_FIELD] = may_contain
    if ingredients is not None:
        gs["Ingredient_Sequence_and_Name"] = ingredients
    return {"data": [{"barcode": int(barcode), "name": name, "gs": gs}]}


class TestCodeDecoding:
    def test_the_real_codes_decode_to_the_closed_list(self):
        product = rami.parse_product(payload(contains=[6807], may_contain=[6821]), BAMBA)
        assert product.contains_ids == ("peanuts",)
        assert product.may_contain_ids == ("soy",)

    def test_the_code_meaning_none_yields_nothing(self):
        """6843 הוא 'אין'. קורלציה ייחסה אותו לקשיו."""
        product = rami.parse_product(payload(contains=[6843]), BAMBA)
        assert product.contains_ids == ()
        assert product.unknown_codes == ()

    def test_the_code_meaning_not_stated_yields_nothing(self):
        """6942 הוא היעדר מידע, ולעולם לא היעדר אלרגן."""
        product = rami.parse_product(payload(contains=[6942]), BAMBA)
        assert product.contains_ids == ()
        assert product.unknown_codes == ()

    def test_gluten_free_oats_do_not_become_gluten(self):
        """6912 הוא שיבולת שועל ללא גלוטן."""
        product = rami.parse_product(payload(contains=[6912]), BAMBA)
        assert "oats" in product.contains_ids
        assert "gluten" not in product.contains_ids

    def test_seafood_covers_both_families(self):
        product = rami.parse_product(payload(contains=[81016]), BAMBA)
        assert set(product.contains_ids) == {"crustaceans", "molluscs"}

    def test_an_unknown_code_is_reported_and_not_swallowed(self):
        product = rami.parse_product(payload(contains=[999999]), BAMBA)
        assert product.contains_ids == ()
        assert product.unknown_codes == ("999999",)


class TestLevelComesFromTheField:
    def test_a_trace_worded_code_in_the_contains_field_stays_contains(self):
        """6825 הוא 'עקבות של בוטנים'. המערכת מחמירה ואינה מקלה לפי ניסוח."""
        product = rami.parse_product(payload(contains=[6825]), BAMBA)
        claims = rami_levy_to_claims(product, IngredientAllergenMap.load(), TODAY)
        peanut = [c for c in claims if c.allergen_id == "peanuts"]
        assert peanut and peanut[0].level is Level.CONTAINS

    def test_the_same_code_in_the_may_contain_field_is_may_contain(self):
        product = rami.parse_product(payload(may_contain=[6825]), BAMBA)
        claims = rami_levy_to_claims(product, IngredientAllergenMap.load(), TODAY)
        peanut = [c for c in claims if c.allergen_id == "peanuts"]
        assert peanut and peanut[0].level is Level.MAY_CONTAIN

    def test_an_allergen_in_both_fields_stays_contains(self):
        product = rami.parse_product(payload(contains=[6807], may_contain=[6807]), BAMBA)
        claims = rami_levy_to_claims(product, IngredientAllergenMap.load(), TODAY)
        peanut = [c for c in claims if c.allergen_id == "peanuts"]
        assert len(peanut) == 1
        assert peanut[0].level is Level.CONTAINS

    def test_levels_are_explicit_and_never_absent(self):
        product = rami.parse_product(payload(contains=[6807], may_contain=[6821]), BAMBA)
        claims = rami_levy_to_claims(product, IngredientAllergenMap.load(), TODAY)
        assert all(not c.level_inferred for c in claims)
        assert all(c.level is not Level.ABSENT for c in claims)
        assert all(c.source is Source.RETAILER for c in claims)


class TestIngredientsAndIdentity:
    def test_hidden_allergens_come_from_the_ingredient_text(self):
        product = rami.parse_product(
            payload(contains=[6807], ingredients="בוטנים טחונים, לציטין סויה, מלח"),
            BAMBA,
        )
        claims = rami_levy_to_claims(product, IngredientAllergenMap.load(), TODAY)
        assert "soy" in {c.allergen_id for c in claims}

    def test_a_product_with_another_barcode_is_rejected(self):
        """הצגת אלרגנים של מוצר שכן היא הטעות שאין לה תיקון."""
        assert rami.parse_product(payload(barcode="7290000000001"), BAMBA) is None

    def test_an_empty_answer_is_not_a_product(self):
        assert rami.parse_product({"data": []}, BAMBA) is None


class TestTheCodeMapItself:
    def test_every_published_code_is_decided(self):
        """כל קוד במילון המקור ממופה או מוחרג במפורש. אין קוד שנשכח."""
        import json
        from pathlib import Path

        base = Path(rami.DEFAULT_CODE_MAP_PATH).parent
        source = json.loads(
            (base / "rami_levy_allergen_codes.json").read_text(encoding="utf-8")
        )
        decided = json.loads(
            (base / "rami_levy_code_map.json").read_text(encoding="utf-8")
        )
        known = set(decided["codes"]) | set(decided["ignored"])
        assert set(source["contains"]) <= known

    def test_no_code_maps_outside_the_closed_list(self):
        import json
        from pathlib import Path

        from allergen_pipeline.domain import allergens

        decided = json.loads(
            Path(rami.DEFAULT_CODE_MAP_PATH).read_text(encoding="utf-8")
        )
        for ids in decided["codes"].values():
            for allergen_id in ids:
                allergens.get(allergen_id)  # מרים חריגה אם אינו ברשימה
