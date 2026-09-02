"""מדיניות המיזוג בין ריצות, ובניית תמונת המצב המקומית."""

from __future__ import annotations

import sqlite3
from datetime import date

from allergen_pipeline.catalog.product import Product
from allergen_pipeline.domain.claims import AllergenClaim, Level, Source
from allergen_pipeline.domain.resolution import resolve
from allergen_pipeline.snapshot import build as snapshot
from allergen_pipeline.text import hebrew
from allergen_pipeline.store import (
    ProductClaims,
    fingerprint_ingredients,
    merge_source_claims,
)

TODAY = date(2026, 9, 2)
LAST_WEEK = date(2026, 8, 26)
BAMBA = "7290000066318"


def claim(allergen_id: str, level: Level, source=Source.MANUFACTURER, on=TODAY):
    return AllergenClaim(
        allergen_id=allergen_id, level=level, source=source, observed_on=on
    )


def existing_claims() -> ProductClaims:
    return ProductClaims(
        barcode=BAMBA,
        claims=[
            claim("peanuts", Level.CONTAINS, on=LAST_WEEK),
            claim("soy", Level.MAY_CONTAIN, Source.OPEN_FOOD_FACTS, on=LAST_WEEK),
        ],
        ingredients_fingerprint=fingerprint_ingredients("בוטנים, תירס"),
    )


class TestNeverDowngrade:
    def test_a_rejected_run_changes_nothing(self):
        outcome = merge_source_claims(
            existing_claims(), Source.MANUFACTURER, incoming=[], run_accepted=False
        )
        assert len(outcome.claims) == 2
        assert outcome.kept_stale_sources == (Source.MANUFACTURER,)

    def test_a_rejected_run_does_not_apply_its_own_results(self):
        outcome = merge_source_claims(
            existing_claims(),
            Source.MANUFACTURER,
            incoming=[claim("milk", Level.CONTAINS)],
            run_accepted=False,
        )
        assert {c.allergen_id for c in outcome.claims} == {"peanuts", "soy"}

    def test_a_source_that_goes_silent_keeps_its_last_good_data(self):
        """הכלל הקריטי: כישלון מקור לא מחזיר מוצר למצב אין מידע."""
        outcome = merge_source_claims(
            existing_claims(), Source.MANUFACTURER, incoming=[], run_accepted=True
        )
        levels = {c.allergen_id: c.level for c in outcome.claims}
        assert levels["peanuts"] is Level.CONTAINS
        assert outcome.needs_review is True
        assert outcome.review_reason and BAMBA in outcome.review_reason

    def test_silence_from_a_source_that_never_reported_is_not_an_incident(self):
        outcome = merge_source_claims(
            existing_claims(), Source.LABEL_EXTRACTION, incoming=[], run_accepted=True
        )
        assert outcome.needs_review is False


class TestSourceReplacement:
    def test_new_results_replace_only_that_source(self):
        outcome = merge_source_claims(
            existing_claims(),
            Source.MANUFACTURER,
            incoming=[claim("milk", Level.CONTAINS)],
            run_accepted=True,
        )
        by_source = {(c.source, c.allergen_id) for c in outcome.claims}
        assert (Source.MANUFACTURER, "milk") in by_source
        assert (Source.MANUFACTURER, "peanuts") not in by_source
        assert (Source.OPEN_FOOD_FACTS, "soy") in by_source

    def test_a_recipe_change_is_flagged(self):
        outcome = merge_source_claims(
            existing_claims(),
            Source.MANUFACTURER,
            incoming=[claim("peanuts", Level.CONTAINS)],
            run_accepted=True,
            incoming_ingredients="בוטנים, תירס, לציטין סויה",
        )
        assert outcome.needs_review is True
        assert "רכיבים" in (outcome.review_reason or "")

    def test_cosmetic_text_changes_are_not_a_recipe_change(self):
        outcome = merge_source_claims(
            existing_claims(),
            Source.MANUFACTURER,
            incoming=[claim("peanuts", Level.CONTAINS)],
            run_accepted=True,
            incoming_ingredients="בוטנים,   תירס",
        )
        assert outcome.needs_review is False

    def test_fingerprints_ignore_punctuation_and_spacing(self):
        assert fingerprint_ingredients("בוטנים, תירס") == fingerprint_ingredients(
            "  בוטנים,,  תירס "
        )

    def test_no_ingredients_has_no_fingerprint(self):
        assert fingerprint_ingredients(None) is None
        assert fingerprint_ingredients("") is None


class TestSnapshot:
    def products(self) -> list[Product]:
        return [
            Product(
                barcode=BAMBA,
                canonical_name="במבה אסם 80 ג",
                manufacturer="אסם",
                department_id="snacks_salty",
                aliases=("חטיף במבה",),
            ),
            Product(
                barcode="7290000072067",
                canonical_name="מוצר ללא מידע",
                department_id="unclassified",
            ),
        ]

    def resolved(self):
        return {
            BAMBA: resolve(
                [
                    claim("peanuts", Level.CONTAINS),
                    claim("soy", Level.MAY_CONTAIN, Source.OPEN_FOOD_FACTS),
                ]
            ),
            "7290000072067": resolve([]),
        }

    def build_snapshot(self, tmp_path):
        path = tmp_path / "snapshot.sqlite"
        stats = snapshot.build(path, self.products(), self.resolved())
        return path, stats

    def test_the_file_is_created_with_both_products(self, tmp_path):
        path, stats = self.build_snapshot(tmp_path)
        assert path.exists()
        assert stats.products == 2

    def test_coverage_counts_only_products_with_data(self, tmp_path):
        _, stats = self.build_snapshot(tmp_path)
        assert stats.with_allergen_data == 1
        assert stats.allergen_coverage == 0.5

    def test_allergen_rows_carry_their_level(self, tmp_path):
        path, _ = self.build_snapshot(tmp_path)
        with sqlite3.connect(path) as connection:
            rows = dict(
                connection.execute(
                    "SELECT allergen_id, level FROM product_allergens WHERE barcode = ?",
                    (BAMBA,),
                ).fetchall()
            )
        assert rows["peanuts"] == "contains"
        assert rows["soy"] == "may_contain"

    def test_absence_of_data_is_absence_of_rows(self, tmp_path):
        """אין מידע מיוצג בהיעדר שורה, ולעולם לא כשורה שאומרת לא מכיל."""
        path, _ = self.build_snapshot(tmp_path)
        with sqlite3.connect(path) as connection:
            count = connection.execute(
                "SELECT COUNT(*) FROM product_allergens WHERE barcode = ?",
                ("7290000072067",),
            ).fetchone()[0]
            flag = connection.execute(
                "SELECT has_allergen_data FROM products WHERE barcode = ?",
                ("7290000072067",),
            ).fetchone()[0]
        assert count == 0
        assert flag == 0

    def test_aliases_are_searchable(self, tmp_path):
        """השאילתה חייבת לעבור אותו נרמול כמו האינדקס, אחרת אות סופית מפילה אותה."""
        path, _ = self.build_snapshot(tmp_path)
        with sqlite3.connect(path) as connection:
            found = connection.execute(
                "SELECT barcode FROM products_fts WHERE products_fts MATCH ?",
                (hebrew.normalize("חטיף"),),
            ).fetchall()
        assert [row[0] for row in found] == [BAMBA]

    def test_an_unnormalised_query_misses(self, tmp_path):
        path, _ = self.build_snapshot(tmp_path)
        with sqlite3.connect(path) as connection:
            found = connection.execute(
                "SELECT barcode FROM products_fts WHERE products_fts MATCH ?",
                ("חטיף",),
            ).fetchall()
        assert found == []

    def test_reference_tables_are_embedded(self, tmp_path):
        path, _ = self.build_snapshot(tmp_path)
        with sqlite3.connect(path) as connection:
            allergen_count = connection.execute(
                "SELECT COUNT(*) FROM allergens"
            ).fetchone()[0]
            department_count = connection.execute(
                "SELECT COUNT(*) FROM departments"
            ).fetchone()[0]
        assert allergen_count > 15
        assert department_count > 15

    def test_meta_records_the_build(self, tmp_path):
        path, _ = self.build_snapshot(tmp_path)
        with sqlite3.connect(path) as connection:
            meta = dict(connection.execute("SELECT key, value FROM meta").fetchall())
        assert meta["schema_version"] == str(snapshot.SCHEMA_VERSION)
        assert meta["product_count"] == "2"

    def test_conflicts_are_written(self, tmp_path):
        path = tmp_path / "conflict.sqlite"
        resolved = {
            BAMBA: resolve(
                [
                    claim("milk", Level.ABSENT),
                    claim("milk", Level.CONTAINS),
                ]
            )
        }
        snapshot.build(path, self.products()[:1], resolved)
        with sqlite3.connect(path) as connection:
            message = connection.execute(
                "SELECT message FROM product_conflicts WHERE barcode = ?", (BAMBA,)
            ).fetchone()[0]
        assert "חלב" in message

    def test_rebuilding_replaces_the_previous_file(self, tmp_path):
        path, _ = self.build_snapshot(tmp_path)
        stats = snapshot.build(path, self.products()[:1], self.resolved())
        assert stats.products == 1
