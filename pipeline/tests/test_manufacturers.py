"""מיפוי יצרנים: נרמול שמות, ממלאי מקום, ואיחוד לקבוצות תאגידיות.

השמות בבדיקות אינם מומצאים. כולם נצפו בפועל בקבצי שקיפות המחירים.
"""

from __future__ import annotations

from allergen_pipeline.catalog import manufacturers


class TestNormalization:
    def test_legal_suffix_is_stripped(self):
        assert manufacturers.normalize_name(
            'תנובה בע"מ'
        ) == manufacturers.normalize_name("תנובה")

    def test_the_suffix_without_quotes_is_also_stripped(self):
        # "בעמ" בלי גרשיים נפוץ בקבצים לא פחות מהצורה התקנית.
        assert manufacturers.normalize_name(
            "יפאורה תבורי בעמ"
        ) == manufacturers.normalize_name("יפאורה תבורי")

    def test_a_cooperative_suffix_is_stripped(self):
        assert manufacturers.normalize_name(
            'סאסאטק אגש"ח בע"מ'
        ) == manufacturers.normalize_name("סאסאטק")

    def test_punctuation_does_not_split_a_company(self):
        assert manufacturers.normalize_name(
            "בית-השיטה תעשיות בע\"מ"
        ) == manufacturers.normalize_name("בית השיטה תעשיות")

    def test_a_suffix_inside_a_name_is_not_stripped(self):
        """הסיומת מוסרת כמילה שלמה בלבד, לא כתת-מחרוזת."""
        assert "אינק" in manufacturers.normalize_name("אינקובטור מזון")

    def test_empty_input(self):
        assert manufacturers.normalize_name(None) == ""
        assert manufacturers.normalize_name("") == ""


class TestPlaceholders:
    def test_generic_values_are_not_manufacturers(self):
        # "כללי" מופיע ב-139 מוצרים בקטלוג ואינו חברה.
        assert manufacturers.is_placeholder("כללי")
        assert manufacturers.is_placeholder("שונות")
        assert manufacturers.is_placeholder("לא ידוע")

    def test_empty_is_a_placeholder(self):
        assert manufacturers.is_placeholder(None)
        assert manufacturers.is_placeholder("   ")

    def test_a_real_company_is_not_a_placeholder(self):
        assert not manufacturers.is_placeholder('תנובה בע"מ')

    def test_a_placeholder_has_no_group(self):
        assert manufacturers.group_of("כללי") is None


class TestGrouping:
    def test_the_four_strauss_entries_land_in_one_group(self):
        names = [
            'שטראוס בריאות בע"מ',
            'שטראוס גרופ בע"מ',
            'שטראוס פריטו ליי בע"מ',
            'גלידת שטראוס בע"מ',
        ]
        groups = {manufacturers.group_of(name) for name in names}
        assert len(groups) == 1
        assert next(iter(groups)).id == "strauss"

    def test_osem_is_recognised(self):
        group = manufacturers.group_of('אסם תעשיות מזון בע"מ')
        assert group is not None and group.id == "osem_nestle"

    def test_an_unknown_company_has_no_group(self):
        assert manufacturers.group_of("תבליני טעם וריח") is None

    def test_matching_is_on_whole_words(self):
        """"עלית" לא אמור לתפוס "מעלית" ו"טרה" לא אמור לתפוס "טרהוילג"."""
        assert manufacturers.group_of("מעלית שירות בעמ") is None
        assert manufacturers.group_of("טרהוילג יבוא") is None


class TestRegistry:
    def catalog(self) -> list[tuple[str, int]]:
        return [
            ('שטראוס גרופ בע"מ', 56),
            ("שטראוס גרופ", 5),
            ('תנובה בע"מ', 161),
            ("כללי", 139),
            ('אסם תעשיות מזון בע"מ', 156),
            ("תבליני טעם וריח", 94),
        ]

    def test_placeholders_are_dropped_from_the_registry(self):
        registry = manufacturers.build_registry(self.catalog())
        assert all(entry.display_name != "כללי" for entry in registry)

    def test_spelling_variants_are_merged(self):
        registry = manufacturers.build_registry(self.catalog())
        strauss = next(e for e in registry if e.group_id == "strauss")
        assert strauss.product_count == 61
        assert len(strauss.raw_names) == 2

    def test_the_registry_is_sorted_by_catalog_weight(self):
        registry = manufacturers.build_registry(self.catalog())
        counts = [entry.product_count for entry in registry]
        assert counts == sorted(counts, reverse=True)

    def test_an_unknown_company_still_gets_an_entry(self):
        """יצרן שאינו בקבוצה מוכרת אינו נעלם; הוא פשוט בלי שיוך."""
        registry = manufacturers.build_registry(self.catalog())
        entry = next(e for e in registry if "טעם וריח" in e.display_name)
        assert entry.group_id is None
        assert entry.product_count == 94

    def test_group_totals_sum_the_variants(self):
        registry = manufacturers.build_registry(self.catalog())
        totals = dict(
            (group.id, count) for group, count in manufacturers.group_totals(registry)
        )
        assert totals["strauss"] == 61
        assert totals["tnuva"] == 161

    def test_an_empty_catalog_yields_an_empty_registry(self):
        assert manufacturers.build_registry([]) == []


class TestProbeFindings:
    """מה שנמדד בפועל מול האתרים, נעול כדי שלא ייעלם בשכתוב."""

    def group(self, group_id: str) -> manufacturers.ManufacturerGroup:
        return next(g for g in manufacturers.GROUPS if g.id == group_id)

    def test_osem_publishes_allergens(self):
        assert self.group("osem_nestle").publishes_allergens is True

    def test_strauss_was_checked_and_does_not(self):
        # ההבחנה בין "נבדק ואינו מפרסם" ל"לא נבדק" חשובה: היא מונעת
        # בדיקה חוזרת של אותו אתר ומתעדת מדוע לא נבנה מתאם.
        strauss = self.group("strauss")
        assert strauss.publishes_allergens is False
        assert strauss.notes

    def test_unverified_sites_have_no_url(self):
        """כתובת שלא אומתה נשארת ריקה, ולא נשמרת כניחוש."""
        for group in manufacturers.GROUPS:
            if group.website is not None:
                assert group.website.startswith("https://")
