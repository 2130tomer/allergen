"""סיווג למחלקות, בחירת שם קנוני, והתנהגות מוצר לאורך זמן."""

from __future__ import annotations

from dataclasses import replace
from datetime import date

from allergen_pipeline.catalog import departments, naming
from allergen_pipeline.text import hebrew
from allergen_pipeline.catalog.product import (
    RetailerOffer,
    build,
    deactivate,
    merge_observation,
)

TODAY = date(2026, 9, 2)
LAST_YEAR = date(2025, 9, 2)
BAMBA = "7290000066318"


def offer(retailer: str, name: str, **kwargs) -> RetailerOffer:
    return RetailerOffer(
        retailer_id=retailer, barcode=BAMBA, raw_name=name, observed_on=TODAY, **kwargs
    )


class TestDepartments:
    def test_the_tree_has_two_levels(self):
        top = departments.top_level()
        assert all(d.parent_id is None for d in top)
        assert departments.children_of("dairy")

    def test_every_child_points_at_a_real_parent(self):
        for department in departments.DEPARTMENTS.values():
            if department.parent_id:
                assert department.parent_id in departments.DEPARTMENTS

    def test_bamba_lands_in_salty_snacks(self):
        assert departments.classify("במבה אסם 80 גרם", "אסם") == "snacks_salty"

    def test_milk_lands_in_dairy(self):
        assert departments.classify("חלב תנובה 3% 1 ליטר") == "dairy_milk"

    def test_bread_lands_in_bakery(self):
        assert departments.classify("לחם אחיד פרוס") == "bakery_bread"

    def test_unmatched_products_are_visibly_unclassified(self):
        # לא נזרק בשקט ל"אחר"; נשאר גלוי כדי שאפשר יהיה לשפר את הכללים.
        assert departments.classify("פריט ללא זיהוי כלשהו") == departments.UNCLASSIFIED_ID

    def test_empty_name_is_unclassified(self):
        assert departments.classify("") == departments.UNCLASSIFIED_ID

    def test_shampoo_is_not_food(self):
        # רשתות המזון מוכרות גם פארם. הפריטים האלה לא נמחקים, כדי שסריקה
        # תמיד תחזיר תשובה, אבל הם לא מופיעים בעיון לפי מחלקות מזון.
        assert departments.classify("שמפו הד אנד שולדרס 700 מל") == departments.NON_FOOD_ID
        assert departments.classify("סכיני גילוח ג'ילט 5 יח") == departments.NON_FOOD_ID
        assert departments.is_non_food("נייר טואלט לילי 32 גליל")

    def test_coconut_cream_is_still_food(self):
        # "קרם" לבדו אינו כלל לא-מזון, בדיוק בגלל המקרה הזה.
        assert not departments.is_non_food("קרם קוקוס 400 מל")

    def test_hebrew_abbreviations_from_real_data_classify(self):
        # קיצורים עם נקודה, כפי שהם מופיעים בקבצים של שופרסל.
        assert departments.classify("שוק.מריר לינדט 70% 100ג") == "snacks_chocolate"
        assert departments.classify("גב.עיזים שום ע.תיבול150ג") == "dairy_cheese"

    def test_plural_forms_classify(self):
        assert departments.classify("נקניקיות עוף 500 גרם") == "meat_processed"

    def test_top_level_of_a_subdepartment(self):
        assert departments.top_level_of("dairy_milk") == "dairy"
        assert departments.top_level_of("dairy") == "dairy"
        assert departments.top_level_of("nonsense") == departments.UNCLASSIFIED_ID


class TestCanonicalNaming:
    def test_the_most_common_name_wins(self):
        names = ["במבה אסם 80 ג", "במבה 80 גרם", "במבה אסם 80 ג"]
        assert naming.canonical_name(names) == "במבה אסם 80 ג"

    def test_a_manufacturer_name_outranks_the_retailers(self):
        names = ["במבה אסם 80 ג", "במבה 80 גרם"]
        assert naming.canonical_name(names, "חטיף במבה קלאסית") == "חטיף במבה קלאסית"

    def test_spelling_variants_are_counted_together(self):
        names = ["קוקה-קולה 1.5 ליטר", "קוקה קולה 1.5 ליטר", "פחית קולה"]
        assert "קוקה" in naming.canonical_name(names)

    def test_other_names_become_aliases(self):
        names = ["במבה אסם 80 ג", "במבה 80 גרם"]
        aliases = naming.aliases(names, "במבה אסם 80 ג")
        assert aliases == ("במבה 80 גרם",)

    def test_aliases_exclude_the_canonical_spelling(self):
        names = ["במבה אסם", "  במבה אסם  "]
        assert naming.aliases(names, "במבה אסם") == ()

    def test_no_names_yields_an_empty_canonical(self):
        assert naming.canonical_name([]) == ""


class TestBarcodeReuse:
    def test_a_completely_different_name_looks_like_reuse(self):
        assert naming.looks_like_barcode_reuse("במבה אסם 80 גרם", "שמפו לשיער יבש")

    def test_a_size_change_is_not_reuse(self):
        assert not naming.looks_like_barcode_reuse(
            "במבה אסם 80 גרם", "במבה אסם 60 גרם"
        )

    def test_missing_names_are_not_treated_as_reuse(self):
        assert not naming.looks_like_barcode_reuse("", "במבה")


class TestProductLifecycle:
    def test_a_product_is_built_from_several_retailers(self):
        product = build(
            BAMBA,
            [
                offer("shufersal", "במבה אסם 80 ג", manufacturer="אסם"),
                offer("rami_levy", "במבה 80 גרם", manufacturer="אסם"),
            ],
        )
        assert product.canonical_name == "במבה אסם 80 ג"
        assert product.manufacturer == "אסם"
        assert product.department_id == "snacks_salty"
        assert set(product.retailer_ids) == {"shufersal", "rami_levy"}

    def test_alias_names_reach_the_search_index(self):
        """האינדקס מנורמל, ולכן גם החיפוש בו חייב לעבור נרמול."""
        product = build(
            BAMBA,
            [
                offer("shufersal", "במבה אסם 80 ג"),
                offer("rami_levy", "חטיף במבה"),
            ],
        )
        assert hebrew.normalize("חטיף") in product.search_text

    def test_merging_keeps_the_original_first_seen_date(self):
        first = replace(
            build(BAMBA, [offer("shufersal", "במבה אסם 80 ג")]),
            first_seen_on=LAST_YEAR,
        )
        second = build(BAMBA, [offer("shufersal", "במבה אסם 80 גרם")])
        merged = merge_observation(first, second)
        assert merged.first_seen_on == LAST_YEAR
        assert merged.needs_review is False

    def test_merging_accumulates_aliases(self):
        first = build(BAMBA, [offer("shufersal", "במבה אסם 80 ג")])
        second = build(BAMBA, [offer("rami_levy", "במבה 80 גרם")])
        merged = merge_observation(first, second)
        assert any("במבה אסם 80 ג" in alias for alias in merged.aliases)

    def test_a_drastic_name_change_flags_the_product_for_review(self):
        first = build(BAMBA, [offer("shufersal", "במבה אסם 80 ג")])
        second = build(BAMBA, [offer("shufersal", "שמפו לשיער יבש 700 מל")])
        merged = merge_observation(first, second)
        assert merged.needs_review is True
        assert merged.review_reason and "מיחזור" in merged.review_reason

    def test_a_vanished_product_stays_in_the_catalog(self):
        product = build(BAMBA, [offer("shufersal", "במבה אסם 80 ג")])
        gone = deactivate(product, TODAY)
        assert gone.is_active is False
        assert gone.barcode == BAMBA

    def test_different_sizes_are_separate_products(self):
        small = build(BAMBA, [offer("shufersal", "במבה אסם 25 ג")])
        large = build("7290000066325", [offer("shufersal", "במבה אסם 80 ג")])
        assert small.barcode != large.barcode
