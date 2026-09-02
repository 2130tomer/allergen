"""בדיקות ליבת התחום: טקסונומיה, קביעות, הכרעה, פירוק ושתי רשימות הסינון."""

from __future__ import annotations

from datetime import date

import pytest

from allergen_pipeline.domain import allergens, flat_list
from allergen_pipeline.domain.claims import (
    AllergenClaim,
    Level,
    Source,
    stricter,
)
from allergen_pipeline.domain.filtering import FilterSelection, Visibility, partition
from allergen_pipeline.domain.resolution import resolve

TODAY = date(2026, 9, 2)
EARLIER = date(2026, 1, 1)


def claim(
    allergen_id: str,
    level: Level,
    source: Source = Source.MANUFACTURER,
    inferred: bool = False,
    on: date = TODAY,
) -> AllergenClaim:
    return AllergenClaim(
        allergen_id=allergen_id,
        level=level,
        source=source,
        observed_on=on,
        level_inferred=inferred,
    )


class TestTaxonomy:
    def test_tree_nuts_have_subtypes(self):
        subtypes = allergens.subtypes_of(allergens.TREE_NUTS_ID)
        assert "cashew" in subtypes
        assert "almond" in subtypes

    def test_selecting_tree_nuts_expands_to_every_subtype(self):
        expanded = allergens.expand_selection({allergens.TREE_NUTS_ID})
        assert "cashew" in expanded
        assert allergens.TREE_NUTS_ID in expanded

    def test_selecting_one_nut_does_not_expand_to_siblings(self):
        expanded = allergens.expand_selection({"cashew"})
        assert expanded == {"cashew"}

    def test_unknown_allergen_id_is_rejected(self):
        with pytest.raises(allergens.UnknownAllergenError):
            allergens.get("kryptonite")

    def test_ancestors_of_subtype(self):
        assert allergens.ancestors_of("cashew") == (allergens.TREE_NUTS_ID,)
        assert allergens.ancestors_of("milk") == ()


class TestClaimGuards:
    def test_non_manufacturer_source_cannot_assert_absence(self):
        # ADR-0002: חילוץ ותרומות יכולים רק להוסיף, לא לשלול.
        with pytest.raises(ValueError):
            claim("milk", Level.ABSENT, Source.LABEL_EXTRACTION)

    def test_manufacturer_may_assert_absence(self):
        assert claim("milk", Level.ABSENT).level is Level.ABSENT

    def test_stricter_prefers_contains(self):
        assert stricter(Level.MAY_CONTAIN, Level.CONTAINS) is Level.CONTAINS
        assert stricter(Level.UNKNOWN, Level.ABSENT) is Level.ABSENT


class TestFlatListDecomposition:
    """המקרה שגילינו באתר אסם: רשימה שטוחה שמוחקת את ההבחנה."""

    def test_bamba_flat_list_is_split_by_ingredients(self):
        claims = flat_list.decompose(
            flat_allergen_ids=["peanuts", "soy"],
            allergens_in_ingredients={"peanuts"},
            source=Source.MANUFACTURER,
            observed_on=TODAY,
        )
        levels = {c.allergen_id: c.level for c in claims}
        assert levels["peanuts"] is Level.CONTAINS
        assert levels["soy"] is Level.MAY_CONTAIN

    def test_every_decomposed_claim_is_marked_inferred(self):
        claims = flat_list.decompose(["soy"], {"peanuts"}, Source.MANUFACTURER, TODAY)
        assert all(c.level_inferred for c in claims)

    def test_without_an_ingredient_list_everything_is_contains(self):
        claims = flat_list.decompose(
            ["peanuts", "soy"], None, Source.MANUFACTURER, TODAY
        )
        assert {c.level for c in claims} == {Level.CONTAINS}

    def test_empty_ingredient_match_still_downgrades(self):
        claims = flat_list.decompose(["soy"], set(), Source.MANUFACTURER, TODAY)
        assert claims[0].level is Level.MAY_CONTAIN

    def test_hidden_allergens_are_explicit_not_inferred(self):
        claims = flat_list.hidden_allergen_claims(
            allergens_in_ingredients={"soy", "milk"},
            declared_allergen_ids={"milk"},
            source=Source.MANUFACTURER,
            observed_on=TODAY,
        )
        assert [c.allergen_id for c in claims] == ["soy"]
        assert claims[0].level is Level.CONTAINS
        assert claims[0].level_inferred is False


class TestResolution:
    def test_bamba_end_to_end(self):
        """אסם נותן רשימה שטוחה, OFF נותן רמות. התוצאה כמו על השקית."""
        manufacturer = flat_list.decompose(
            ["peanuts", "soy"], {"peanuts"}, Source.MANUFACTURER, TODAY
        )
        off = [
            claim("peanuts", Level.CONTAINS, Source.OPEN_FOOD_FACTS),
            claim("soy", Level.MAY_CONTAIN, Source.OPEN_FOOD_FACTS),
        ]
        resolved = resolve(manufacturer + off)
        assert resolved.level_of("peanuts") is Level.CONTAINS
        assert resolved.level_of("soy") is Level.MAY_CONTAIN

    def test_explicit_level_beats_inferred_level_from_higher_tier(self):
        # ADR-0004: היצרן גובר על זהות האלרגן, לא בהכרח על רמתו.
        inferred_contains = claim(
            "soy", Level.CONTAINS, Source.MANUFACTURER, inferred=True
        )
        explicit_may = claim("soy", Level.MAY_CONTAIN, Source.OPEN_FOOD_FACTS)
        resolved = resolve([inferred_contains, explicit_may])
        assert resolved.level_of("soy") is Level.MAY_CONTAIN

    def test_higher_tier_wins_when_both_are_explicit(self):
        resolved = resolve(
            [
                claim("soy", Level.CONTAINS, Source.MANUFACTURER),
                claim("soy", Level.MAY_CONTAIN, Source.OPEN_FOOD_FACTS),
            ]
        )
        assert resolved.level_of("soy") is Level.CONTAINS

    def test_equal_standing_resolves_to_the_stricter_level(self):
        resolved = resolve(
            [
                claim("soy", Level.MAY_CONTAIN, Source.OPEN_FOOD_FACTS),
                claim("soy", Level.CONTAINS, Source.OPEN_FOOD_FACTS),
            ]
        )
        assert resolved.level_of("soy") is Level.CONTAINS

    def test_missing_allergen_is_unknown_not_absent(self):
        resolved = resolve([claim("peanuts", Level.CONTAINS)])
        assert resolved.level_of("milk") is Level.UNKNOWN
        assert "milk" in resolved.unknown_ids()

    def test_no_claims_at_all_means_no_data(self):
        assert resolve([]).has_any_data is False

    def test_conflict_between_declaration_and_ingredients(self):
        """היצרן מצהיר לא מכיל חלב, הרכיבים אומרים אבקת חלב."""
        resolved = resolve(
            [
                claim("milk", Level.ABSENT, Source.MANUFACTURER),
                claim("milk", Level.CONTAINS, Source.MANUFACTURER),
            ]
        )
        assert resolved.level_of("milk") is Level.CONTAINS
        assert len(resolved.conflicts) == 1
        assert "חלב" in resolved.conflicts[0].message_he

    def test_lower_tier_positive_overrides_manufacturer_absence(self):
        resolved = resolve(
            [
                claim("peanuts", Level.ABSENT, Source.MANUFACTURER),
                claim("peanuts", Level.MAY_CONTAIN, Source.USER),
            ]
        )
        assert resolved.level_of("peanuts") is Level.MAY_CONTAIN
        assert resolved.conflicts

    def test_absence_alone_resolves_to_absent(self):
        resolved = resolve([claim("milk", Level.ABSENT)])
        assert resolved.level_of("milk") is Level.ABSENT
        assert not resolved.conflicts

    def test_subtype_propagates_up_to_tree_nuts(self):
        resolved = resolve([claim("cashew", Level.CONTAINS)])
        assert resolved.level_of(allergens.TREE_NUTS_ID) is Level.CONTAINS
        assert resolved.by_allergen[allergens.TREE_NUTS_ID].inherited_from == "cashew"

    def test_parent_claim_does_not_propagate_down(self):
        resolved = resolve([claim(allergens.TREE_NUTS_ID, Level.CONTAINS)])
        assert resolved.level_of("cashew") is Level.UNKNOWN

    def test_parent_takes_the_stricter_of_its_children(self):
        resolved = resolve(
            [
                claim("cashew", Level.MAY_CONTAIN),
                claim("almond", Level.CONTAINS),
            ]
        )
        assert resolved.level_of(allergens.TREE_NUTS_ID) is Level.CONTAINS

    def test_latest_observation_is_reported(self):
        resolved = resolve(
            [
                claim("milk", Level.CONTAINS, on=EARLIER),
                claim("soy", Level.CONTAINS, on=TODAY),
            ]
        )
        assert resolved.latest_observed_on == TODAY


class TestFiltering:
    def bamba(self):
        return resolve(
            [
                claim("peanuts", Level.CONTAINS),
                claim("soy", Level.MAY_CONTAIN),
            ]
        )

    def test_empty_selection_shows_everything(self):
        assert FilterSelection().apply(self.bamba()).is_visible

    def test_contains_list_hides_a_matching_product(self):
        selection = FilterSelection(contains_exclusions=frozenset({"peanuts"}))
        outcome = selection.apply(self.bamba())
        assert outcome.visibility is Visibility.HIDDEN
        assert outcome.matched_allergen_ids == ("peanuts",)

    def test_may_contain_list_hides_a_matching_product(self):
        selection = FilterSelection(may_contain_exclusions=frozenset({"soy"}))
        assert selection.apply(self.bamba()).visibility is Visibility.HIDDEN

    def test_the_two_lists_are_independent(self):
        """סימון סויה ברשימת מכיל בלבד אינו מסתיר מוצר שרק עלול להכיל."""
        selection = FilterSelection(contains_exclusions=frozenset({"soy"}))
        assert selection.apply(self.bamba()).is_visible

    def test_may_contain_only_selection_still_shows_products_that_contain(self):
        selection = FilterSelection(may_contain_exclusions=frozenset({"peanuts"}))
        assert selection.apply(self.bamba()).is_visible

    def test_that_gap_produces_an_explicit_warning(self):
        selection = FilterSelection(may_contain_exclusions=frozenset({"peanuts"}))
        warnings = selection.warnings()
        assert len(warnings) == 1
        assert "בוטנים" in warnings[0].message_he

    def test_no_warning_when_both_lists_agree(self):
        selection = FilterSelection(
            contains_exclusions=frozenset({"peanuts"}),
            may_contain_exclusions=frozenset({"peanuts"}),
        )
        assert selection.warnings() == ()

    def test_product_without_data_goes_to_the_unknown_bucket(self):
        selection = FilterSelection(contains_exclusions=frozenset({"milk"}))
        outcome = selection.apply(resolve([]))
        assert outcome.visibility is Visibility.UNKNOWN
        assert outcome.unknown_allergen_ids == ("milk",)

    def test_known_absence_is_visible_not_unknown(self):
        selection = FilterSelection(contains_exclusions=frozenset({"milk"}))
        assert selection.apply(resolve([claim("milk", Level.ABSENT)])).is_visible

    def test_selecting_tree_nuts_hides_a_cashew_product(self):
        selection = FilterSelection(
            contains_exclusions=frozenset({allergens.TREE_NUTS_ID})
        )
        outcome = selection.apply(resolve([claim("cashew", Level.CONTAINS)]))
        assert outcome.visibility is Visibility.HIDDEN

    def test_selection_is_known_via_a_subtype(self):
        selection = FilterSelection(
            contains_exclusions=frozenset({allergens.TREE_NUTS_ID})
        )
        outcome = selection.apply(resolve([claim("cashew", Level.ABSENT)]))
        assert outcome.is_visible

    def test_partition_separates_the_three_groups(self):
        selection = FilterSelection(contains_exclusions=frozenset({"peanuts"}))
        products = [
            ("hidden", resolve([claim("peanuts", Level.CONTAINS)])),
            ("visible", resolve([claim("peanuts", Level.ABSENT)])),
            ("unknown", resolve([])),
        ]
        result = partition(selection, products)
        assert result.visible == ["visible"]
        assert result.unknown == ["unknown"]
        assert result.hidden_count == 1
        assert result.total_shown == 2

    def test_invalid_allergen_in_selection_is_rejected(self):
        with pytest.raises(allergens.UnknownAllergenError):
            FilterSelection(contains_exclusions=frozenset({"nope"}))
