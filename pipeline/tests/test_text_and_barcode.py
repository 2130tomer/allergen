"""נרמול עברי, זיהוי סוג שאילתה, ואימות ברקודים."""

from __future__ import annotations

from allergen_pipeline.catalog import barcode
from allergen_pipeline.text import hebrew

BAMBA = "7290000066318"


class TestNormalization:
    def test_quotes_are_dropped(self):
        assert hebrew.normalize('"במבה"') == hebrew.normalize("במבה")

    def test_gershayim_is_dropped(self):
        assert hebrew.normalize("ק״ג") == hebrew.normalize("קג")

    def test_hyphen_becomes_a_space(self):
        assert hebrew.normalize("קוקה-קולה") == hebrew.normalize("קוקה קולה")

    def test_niqqud_is_stripped(self):
        assert hebrew.normalize("בַּמְבָּה") == hebrew.normalize("במבה")

    def test_final_letters_are_unified(self):
        assert hebrew.normalize("לחם") == hebrew.normalize("לחמ")

    def test_digits_glued_to_letters_are_separated(self):
        """נפוץ מאוד בקבצי הרשתות: 100ג, 32יח, 5סכיני."""
        assert hebrew.tokenize("במבה 100ג") == ["במבה", "100", "ג"]
        assert hebrew.tokenize("5סכיני גילוח") == ["5", "סכיני", "גילוח"]
        assert hebrew.tokenize("קלינקס 12*9יח") == ["קלינקס", "12", "9", "יח"]

    def test_separating_digits_makes_the_word_findable(self):
        assert hebrew.normalize("שוק.מריר לינדט 70% 100ג").split() == [
            "שוק",
            "מריר",
            "לינדט",
            "70",
            "100",
            "ג",
        ]

    def test_whitespace_is_collapsed(self):
        assert hebrew.normalize("  במבה   אסם  ") == "במבה אסמ"

    def test_latin_is_lowercased(self):
        assert hebrew.normalize("Coca Cola") == "coca cola"

    def test_empty_input(self):
        assert hebrew.normalize("") == ""
        assert hebrew.tokenize(None or "") == []


class TestPrefixHandling:
    def test_prefix_is_stripped_when_a_real_stem_remains(self):
        assert hebrew.strip_prefix(hebrew.normalize("בלחם")) == hebrew.normalize("לחם")

    def test_short_words_are_never_mutilated(self):
        # "מלח" חייב להישאר מלח ולא להפוך ל"לח".
        assert hebrew.strip_prefix(hebrew.normalize("מלח")) is None

    def test_variants_keep_the_original_token(self):
        variants = hebrew.token_variants(hebrew.normalize("בלחם"))
        assert hebrew.normalize("בלחם") in variants
        assert hebrew.normalize("לחם") in variants

    def test_index_text_covers_every_source_field(self):
        indexed = hebrew.index_text("במבה", "אסם", "חטיף במבה קלאסי")
        assert "במבה" in indexed
        assert hebrew.normalize("אסם") in indexed

    def test_index_text_ignores_empty_fields(self):
        assert hebrew.index_text("במבה", None, "") == hebrew.index_text("במבה")


class TestQueryKind:
    def test_a_full_barcode_is_recognised(self):
        assert hebrew.looks_like_barcode(BAMBA)

    def test_separators_inside_a_barcode_are_tolerated(self):
        assert hebrew.looks_like_barcode("729 0000 066318")

    def test_short_digit_strings_are_free_text(self):
        assert not hebrew.looks_like_barcode("1234")

    def test_too_long_digit_strings_are_free_text(self):
        assert not hebrew.looks_like_barcode("1" * 15)

    def test_hebrew_is_free_text(self):
        assert not hebrew.looks_like_barcode("במבה")

    def test_mixed_input_is_free_text(self):
        assert not hebrew.looks_like_barcode("במבה 7290000066318")

    def test_empty_is_not_a_barcode(self):
        assert not hebrew.looks_like_barcode("")


class TestBarcodeValidation:
    def test_the_bamba_barcode_validates(self):
        assert barcode.is_valid_gtin(BAMBA)

    def test_a_wrong_check_digit_is_rejected(self):
        assert not barcode.is_valid_gtin("7290000066319")

    def test_check_digit_is_computed_correctly(self):
        assert barcode.check_digit(BAMBA) == 8

    def test_wrong_length_is_rejected(self):
        assert not barcode.is_valid_gtin("729000006")

    def test_internal_retailer_codes_are_not_usable(self):
        # קידומת 2 שמורה לשימוש פנימי ואינה מזהה מוצר מחוץ לרשת.
        internal = "2" + BAMBA[1:12]
        internal += str(barcode.check_digit(internal + "0"))
        assert barcode.is_internal(internal)
        assert not barcode.is_usable(internal)

    def test_usable_requires_both_checks(self):
        assert barcode.is_usable(BAMBA)
        assert not barcode.is_usable("")
        assert not barcode.is_usable(None)

    def test_gtin14_with_leading_zero_collapses_to_13(self):
        assert barcode.to_gtin13("0" + BAMBA) == BAMBA

    def test_normalize_keeps_digits_only(self):
        assert barcode.normalize(" 729-0000 066318 ") == BAMBA
