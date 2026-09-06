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

    def test_household_goods_from_the_unclassified_pile_are_not_food(self):
        """פריטים אמיתיים שנצפו בקטלוג ונשארו לא מסווגים.

        רשתות המזון מוכרות גם כלי בית וחשמל. כל עוד הם לא מסווגים הם
        נספרים כמוצרי מזון שאין עליהם מידע אלרגנים, וזה מנפח את מספר
        חסרי המידע ומקשה למצוא מוצר אמיתי בעיון.
        """
        for name in [
            "סט מזוודות בד 4 גלגל",
            "מקפיא נופרוסט 7 מגיר",
            "טלפון לתינוק",
            "שעון שבת",
            "באנר אותיות יום הולד",
            "מפיץ ריח 100 מ\"ל AYL",
            "מבשם WHITE SAND",
            "קולגייט משחת ילדים 0",
            "גליל מפה אלבד ורוד 1",
        ]:
            assert departments.is_non_food(name), name

    def test_toiletries_and_housewares_from_the_catalog_are_not_food(self):
        """פריטים שנצפו בקטלוג, חלקם מסווגים היום למחלקת מזון בטעות.

        "ת.רחצה מלפפון" ישב ב"פירות וירקות" בגלל המלפפון, ו"קלמר גלידה"
        ישב בקינוחים. המונחים האלה גם מסווגים את הלא-מסווגים וגם
        מתקנים את השיוכים השגויים.
        """
        for name in [
            "תחליב רחצה שמן ארגן 700",
            "ת.רחצה מלפפון750מ לה מון",
            "גליס שמן לשיער 75 מל",
            "קלמר 2 תא גלידה ורוד",
            "פורס ביצים פלסטיק",
            "גל גילוח סירייס גיל",
            "צבע לשיער לוריאל 5",
        ]:
            assert departments.is_non_food(name), name

    def test_food_that_shares_a_word_with_those_terms_stays_food(self):
        """המונחים שנפסלו בבדיקה הזו, ולמה.

        "ספריי" נראה כמו מוצר ניקיון אך "אושן ספריי חמוציות" הוא משקה,
        ו"כוס" מופיעה ב"נמס בכוס פטריות". שניהם לא נכנסו לרשימה.
        """
        for name in [
            "אושן ספריי חמוציות דיאט",
            "נמס בכוס פטריות 43ג",
            "שמן זית כתית מעולה 750",
        ]:
            assert not departments.is_non_food(name), name

    def test_real_food_is_never_marked_as_non_food(self):
        """הכיוון המסוכן.

        סימון מזון כלא-מזון מסתיר את טבלת האלרגנים שלו לגמרי, ולכן כל
        מונח שנוסף לרשימת הלא-מזון חייב להיות מונח שאינו יכול להופיע
        במזון. הפריטים כאן נצפו באותו ערימת הלא-מסווגים.
        """
        for name in [
            "כדורי חלבה+מייפל כשלפ230",
            "טילון אוראו",
            "קורנפלור 200 גרם",
            "כרוב אדום שלם חסלט ב",
            "תן צאפ ציפס ברביקיו",
            "צילי כתוש חריף 30 גרם",
            "גלידות נסטלה",
            "פרי מבורך אפונת גינה",
            "שמן זית כתית מעולה 750",
            "מרק עוף ביתי קפוא",
            # חמשת אלה נצפו בקטלוג והפילו מונחים שנוסו ונפסלו.
            "עוגיות אוזניות 500 גרם",
            "לוקיטוס שטיחים חמוצי",
            "עוגיות אלפחורס מקרר",
            "כריות מולאו שוקולד 375",
            "פופקורן למיקרוגל חמאה",
        ]:
            assert not departments.is_non_food(name), name

    def test_free_from_shelf_beats_the_food_type(self):
        """מי שמסנן גלוטן מחפש את המדף הייעודי, לא את מדף הלחם.

        הכלל היה אחרון ולכן "לחם ללא גלוטן" נתפס ככלל הלחם. זו נראות
        בלבד: הסיווג אינו מסמן דבר בירוק ואינו מייצר קביעת היעדר.
        """
        assert departments.classify("לחם לבן ללא גלוטן 500 גר") == "health_free_from"
        assert departments.classify("בצק לפיצה ללא גלוטן230ג") == "health_free_from"
        assert departments.classify("חלב נטול לקטוז 1 ליטר") == "health_free_from"
        # מוצר רגיל מאותה משפחה נשאר במחלקת המזון שלו.
        assert departments.classify("לחם אחיד פרוס") == "bakery_bread"

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
