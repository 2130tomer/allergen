"""מתאמי המקורות: קבצי שקיפות מחירים, אתר יצרן, ו-Open Food Facts."""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

import pytest

from allergen_pipeline.domain.claims import Level, Source
from allergen_pipeline.ingredients.mapping import IngredientAllergenMap
from allergen_pipeline.sources import openfoodfacts as off
from allergen_pipeline.sources.base import (
    RunStats,
    SanityCheckFailed,
    check_run,
    is_stale,
)
from allergen_pipeline.sources.manufacturers import base as manufacturer_base
from allergen_pipeline.sources.manufacturers import osem
from allergen_pipeline.sources.price_transparency import parser, retailers

TODAY = date(2026, 9, 2)
BAMBA = "7290000066318"

PRICE_XML = """<?xml version="1.0" encoding="utf-8"?>
<Root>
  <ChainId>7290027600007</ChainId>
  <StoreId>001</StoreId>
  <Items Count="4">
    <Item>
      <ItemCode>7290000066318</ItemCode>
      <ItemType>1</ItemType>
      <ItemName>במבה אסם 80 גרם</ItemName>
      <ManufacturerName>אסם</ManufacturerName>
      <Quantity>80</Quantity>
      <UnitQty>גרם</UnitQty>
      <ItemInternalCode>445566</ItemInternalCode>
      <PriceUpdateDate>2026-09-01 10:00:00</PriceUpdateDate>
    </Item>
    <Item>
      <ItemCode>1234</ItemCode>
      <ItemType>1</ItemType>
      <ItemName>פריט עם ברקוד שבור</ItemName>
    </Item>
    <Item>
      <ItemCode>7290000066318</ItemCode>
      <ItemType>0</ItemType>
      <ItemName>עגבניות שקיל</ItemName>
    </Item>
    <Item>
      <ItemCode>7290000072067</ItemCode>
      <ItemType>1</ItemType>
      <ItemName>ביסלי גריל 70 גרם</ItemName>
      <ManufacturerName>אסם</ManufacturerName>
    </Item>
  </Items>
</Root>
"""

# מבנה אמיתי מקובץ PriceFull של שופרסל. שמות התגיות כאן אינם המצאה:
# ManufactureName ולא ManufacturerName, PriceUpdateTime ולא PriceUpdateDate,
# ותאריך ISO עם T. שלושתם נשברו בהרצה הראשונה על נתונים אמיתיים.
SHUFERSAL_REAL_XML = """<Root>
  <ChainID>7290027600007</ChainID>
  <SubChainID>001</SubChainID>
  <StoreID>001</StoreID>
  <BikoretNo>9</BikoretNo>
  <Items>
    <Item>
      <PriceUpdateTime>2025-12-28T14:15:00</PriceUpdateTime>
      <ItemCode>7290000066318</ItemCode>
      <LastSaleDateTime>2026-09-01T20:08:28</LastSaleDateTime>
      <ItemType>1</ItemType>
      <ItemName>במבה אסם 80 גרם</ItemName>
      <ManufactureName>אסם</ManufactureName>
      <ManufactureCountry>IL</ManufactureCountry>
      <ManufactureItemDescription>חטיף במבה</ManufactureItemDescription>
      <UnitQty>גרם</UnitQty>
      <Quantity>80.00</Quantity>
      <UnitOfMeasure>גרם</UnitOfMeasure>
      <bIsWeighted>0</bIsWeighted>
      <QtyInPackage>1</QtyInPackage>
      <ItemPrice>5.90</ItemPrice>
      <ItemStatus />
    </Item>
    <Item>
      <PriceUpdateTime>2024-12-31T12:36:00</PriceUpdateTime>
      <ItemCode>10900302814</ItemCode>
      <ItemType>1</ItemType>
      <ItemName>ניילון נצמד</ItemName>
      <ManufactureName>ריינולדס</ManufactureName>
    </Item>
  </Items>
</Root>
"""

OSEM_HTML = """
<html><body>
  <h1>חטיף במבה קלאסית</h1>
  <img src="https://www.osem-nestle.co.il/sites/site.prod.osem-nestle.co.il/files/product_images_new/12532883_7290000066318_1_Enlarge.jpg?v=1788354693" />
  <div class="panel">
    <h2 class="panel-title">רשימת מרכיבים</h2>
    <div class="panel-body">בוטנים טחונים (54%), גריסי תירס, שמן חמניות, מלח, ויטמינים</div>
  </div>
  <div class="panel">
    <h2 class="panel-title">אלרגנים</h2>
    <div class="panel-body">בוטנים סויה</div>
  </div>
  <div class="panel">
    <h2 class="panel-title">מידע תזונתי</h2>
    <div class="panel-body">אנרגיה 534 קלוריות</div>
  </div>
</body></html>
"""

OFF_PAYLOAD = {
    "status": 1,
    "code": BAMBA,
    "product": {
        "code": BAMBA,
        "product_name": "במבה",
        "brands": "אסם",
        "allergens_tags": ["en:בוטנים"],
        "traces_tags": ["en:soybeans"],
        "ingredients_text_he": "בוטנים טחונים (54%) גריסי תירס שמן חמניות מלח",
        "image_front_url": "https://images.openfoodfacts.org/bamba.jpg",
    },
}


@pytest.fixture(scope="module")
def ingredient_map() -> IngredientAllergenMap:
    return IngredientAllergenMap.load()


class TestPriceTransparencyParsing:
    def parsed(self):
        return parser.parse_bytes(PRICE_XML.encode("utf-8"), "shufersal", TODAY)

    def test_valid_items_become_offers(self):
        assert len(self.parsed().offers) == 2

    def test_fields_are_read(self):
        bamba = next(o for o in self.parsed().offers if o.barcode == BAMBA)
        assert bamba.raw_name == "במבה אסם 80 גרם"
        assert bamba.manufacturer == "אסם"
        assert bamba.quantity == "80"
        assert bamba.retailer_sku == "445566"
        assert bamba.observed_on == date(2026, 9, 1)

    def test_broken_barcodes_are_dropped(self):
        assert self.parsed().skipped_invalid_barcode == 1

    def test_weighted_items_are_dropped(self):
        assert self.parsed().skipped_weighted == 1

    def test_store_id_is_read_from_the_header(self):
        assert self.parsed().store_id == "001"

    def test_a_bom_prefixed_file_still_parses(self):
        data = b"\xef\xbb\xbf" + PRICE_XML.encode("utf-8")
        assert parser.parse_bytes(data, "shufersal", TODAY).offers

    def test_tag_names_are_matched_case_insensitively(self):
        lowered = PRICE_XML.replace("ItemCode", "itemcode").replace(
            "ItemName", "itemname"
        )
        assert parser.parse_bytes(lowered.encode("utf-8"), "shufersal", TODAY).offers


class TestShufersalRealFormat:
    """רגרסיה מול המבנה שנצפה בפועל בקובץ של שופרסל."""

    def parsed(self):
        return parser.parse_bytes(
            SHUFERSAL_REAL_XML.encode("utf-8"), "shufersal", TODAY
        )

    def test_the_manufacturer_name_is_read(self):
        # התגית היא ManufactureName, בלי ה-r. בלי האליאס הזה כל שמות
        # היצרנים חוזרים ריקים והקטלוג נראה תקין למרות שהוא לא.
        bamba = next(o for o in self.parsed().offers if o.barcode == BAMBA)
        assert bamba.manufacturer == "אסם"

    def test_the_iso_update_time_is_parsed(self):
        bamba = next(o for o in self.parsed().offers if o.barcode == BAMBA)
        assert bamba.observed_on == date(2025, 12, 28)

    def test_an_eleven_digit_internal_code_is_rejected(self):
        # 11 ספרות אינו אורך GTIN חוקי; זהו קוד פנימי ולא מזהה מוצר.
        assert all(o.barcode != "10900302814" for o in self.parsed().offers)
        assert self.parsed().skipped_invalid_barcode == 1


# מבנה אמיתי מקובץ PriceFull של רמי לוי. אותן תגיות כמו שופרסל, אבל
# הערכים עצמם הם מציין-מקום, והתאריך כולל אלפיות שנייה.
RAMI_LEVY_REAL_XML = """<Root>
  <ChainID>7290058140886</ChainID>
  <StoreID>001</StoreID>
  <Items>
    <Item>
      <PriceUpdateTime>2025-02-18T15:52:25.000</PriceUpdateTime>
      <ItemCode>7290017023212</ItemCode>
      <ItemType>1</ItemType>
      <ItemName>רביעיית פחיות שוופס</ItemName>
      <ManufactureName>לא ידוע</ManufactureName>
      <ManufactureCountry>לא ידוע</ManufactureCountry>
      <UnitQty>לא ידוע</UnitQty>
      <Quantity>1.32</Quantity>
      <UnitOfMeasure>ליטר</UnitOfMeasure>
      <QtyInPackage>לא ידוע</QtyInPackage>
    </Item>
  </Items>
</Root>
"""


class TestRamiLevyRealFormat:
    """רגרסיה מול המבנה שנצפה בפועל בקובץ של רמי לוי."""

    def offer(self):
        parsed = parser.parse_bytes(
            RAMI_LEVY_REAL_XML.encode("utf-8"), "rami_levy", TODAY
        )
        return parsed.offers[0]

    def test_the_placeholder_manufacturer_is_read_as_missing(self):
        # בלי זה "לא ידוע" הופך לשם היצרן הנפוץ ביותר בקטלוג.
        assert self.offer().manufacturer is None

    def test_a_placeholder_falls_through_to_the_next_alias(self):
        # UnitQty הוא "לא ידוע", אבל UnitOfMeasure מכיל "ליטר" אמיתי.
        # מציין-מקום אינו עוצר את החיפוש; הוא מדלג לאליאס הבא.
        assert self.offer().unit == "ליטר"

    def test_a_timestamp_with_milliseconds_is_parsed(self):
        assert self.offer().observed_on == date(2025, 2, 18)

    def test_the_product_itself_is_still_kept(self):
        """מוצר עם שדות חסרים הוא עדיין מוצר. הוא לא נזרק מהקטלוג."""
        assert self.offer().barcode == "7290017023212"
        assert self.offer().raw_name == "רביעיית פחיות שוופס"


class TestRetailerConfig:
    def test_shufersal_and_rami_levy_come_first(self):
        first_two = [r.id for r in retailers.enabled_for_stage(1)]
        assert first_two == ["shufersal", "rami_levy"]

    def test_later_stages_include_everyone(self):
        assert len(retailers.enabled_for_stage(2)) == len(retailers.RETAILERS)

    def test_the_shared_portal_needs_a_username(self):
        assert retailers.BY_ID["rami_levy"].requires_login
        assert retailers.BY_ID["rami_levy"].username
        assert not retailers.BY_ID["shufersal"].requires_login


class TestSanityChecks:
    def stats(self, rows: int, missing: int = 0) -> RunStats:
        now = datetime.now()
        return RunStats("test", rows=rows, started_at=now, finished_at=now, missing_required=missing)

    def test_an_empty_run_is_rejected(self):
        with pytest.raises(SanityCheckFailed):
            check_run(self.stats(0))

    def test_a_collapsed_row_count_is_rejected(self):
        with pytest.raises(SanityCheckFailed):
            check_run(self.stats(100), previous_rows=1000)

    def test_a_normal_fluctuation_passes(self):
        check_run(self.stats(950), previous_rows=1000)

    def test_widespread_missing_fields_are_rejected(self):
        with pytest.raises(SanityCheckFailed):
            check_run(self.stats(100, missing=50))

    def test_a_silent_adapter_is_stale(self):
        assert is_stale(None, TODAY)
        assert is_stale(date(2026, 8, 1), TODAY)
        assert not is_stale(date(2026, 9, 1), TODAY)


class TestOsemAdapter:
    def test_the_barcode_comes_from_the_image_filename(self):
        assert osem.extract_barcode(OSEM_HTML) == BAMBA

    def test_no_image_means_no_barcode(self):
        assert osem.extract_barcode("<html><body>אין תמונה</body></html>") is None

    def test_the_allergen_panel_is_read(self):
        product = osem.parse_product_page(OSEM_HTML, "https://example.test/bamba")
        assert "בוטנים" in product.raw_allergen_terms
        assert "סויה" in product.raw_allergen_terms

    def test_the_ingredient_panel_is_read(self):
        product = osem.parse_product_page(OSEM_HTML, "https://example.test/bamba")
        assert product.ingredients_text and "גריסי תירס" in product.ingredients_text

    def test_the_nutrition_panel_does_not_leak_into_allergens(self):
        product = osem.parse_product_page(OSEM_HTML, "https://example.test/bamba")
        assert not any("קלוריות" in term for term in product.raw_allergen_terms)

    def test_the_product_name_is_read(self):
        product = osem.parse_product_page(OSEM_HTML, "https://example.test/bamba")
        assert product.product_name == "חטיף במבה קלאסית"

    def test_the_flat_list_is_split_correctly(self, ingredient_map):
        """הבדיקה המרכזית: 'בוטנים סויה' הופך למכיל בוטנים, עלול להכיל סויה."""
        product = osem.parse_product_page(OSEM_HTML, "https://example.test/bamba")
        claims = manufacturer_base.to_claims(product, ingredient_map, TODAY)
        levels = {c.allergen_id: c.level for c in claims}
        assert levels["peanuts"] is Level.CONTAINS
        assert levels["soy"] is Level.MAY_CONTAIN

    def test_a_page_without_a_barcode_yields_no_claims(self, ingredient_map):
        # כלל הברזל: אין קישור ודאי לברקוד, אין שיוך אלרגנים.
        product = osem.parse_product_page(
            OSEM_HTML.replace("product_images_new", "banner_images"),
            "https://example.test/bamba",
        )
        assert product.is_linkable is False
        assert manufacturer_base.to_claims(product, ingredient_map, TODAY) == []


class TestOsemAgainstTheRealPage:
    """מקבע שנחתך מדף מוצר אמיתי של אסם-נסטלה, לא מ-HTML שהומצא.

    זו הבדיקה שמוכיחה שהמנגנון של ADR-0004 עובד על נתוני יצרן אמיתיים:
    האתר מפרסם "בוטנים סויה" בשורה אחת, וההצלבה מול הרכיבים משחזרת את
    ההבחנה שהמוצר מכיל בוטנים ורק עלול להכיל סויה.
    """

    def page(self) -> str:
        fixture = Path(__file__).parent / "fixtures" / "osem_bamba_real.html"
        return fixture.read_text(encoding="utf-8")

    def product(self):
        return osem.parse_product_page(self.page(), "https://example.test/bamba")

    def test_the_barcode_is_recovered_from_the_image_path(self):
        assert self.product().barcode == "7290001302279"

    def test_the_real_ingredient_text_is_read(self):
        ingredients = self.product().ingredients_text or ""
        assert "בוטנים טחונים" in ingredients
        assert "גריסי תירס" in ingredients

    def test_the_flat_allergen_line_is_read_verbatim(self):
        assert "בוטנים סויה" in self.product().raw_allergen_terms

    def test_a_repeated_panel_is_not_concatenated(self):
        """הדף האמיתי חוזר על פאנל האלרגנים, ואסור שייווצר כפל טקסט."""
        terms = self.product().raw_allergen_terms
        assert not any("בוטנים סויה בוטנים" in term for term in terms)

    def test_the_flat_line_resolves_to_two_different_levels(self, ingredient_map):
        claims = manufacturer_base.to_claims(
            self.product(), ingredient_map, TODAY
        )
        levels = {claim.allergen_id: claim.level for claim in claims}
        assert levels["peanuts"] is Level.CONTAINS
        assert levels["soy"] is Level.MAY_CONTAIN

    def test_both_levels_are_marked_inferred(self, ingredient_map):
        """נגזרו מהצלבה, ולכן קביעה מפורשת ממקור אחר תגבר עליהן."""
        claims = manufacturer_base.to_claims(
            self.product(), ingredient_map, TODAY
        )
        assert all(claim.level_inferred for claim in claims)


class TestOpenFoodFacts:
    def test_a_found_product_is_parsed(self):
        product = off.parse_product(OFF_PAYLOAD)
        assert product is not None
        assert product.barcode == BAMBA
        assert product.brands == "אסם"

    def test_a_missing_product_returns_nothing(self):
        assert off.parse_product({"status": 0}) is None

    def test_hebrew_and_english_tags_both_map(self):
        product = off.parse_product(OFF_PAYLOAD)
        assert product.allergen_ids == ("peanuts",)
        assert product.trace_ids == ("soy",)

    def test_levels_are_explicit_and_not_inferred(self):
        product = off.parse_product(OFF_PAYLOAD)
        claims = off.to_claims(product, TODAY)
        assert all(not c.level_inferred for c in claims)
        assert all(c.source is Source.OPEN_FOOD_FACTS for c in claims)

    def test_traces_become_may_contain(self):
        claims = off.to_claims(off.parse_product(OFF_PAYLOAD), TODAY)
        levels = {c.allergen_id: c.level for c in claims}
        assert levels["peanuts"] is Level.CONTAINS
        assert levels["soy"] is Level.MAY_CONTAIN

    def test_an_allergen_in_both_fields_stays_contains(self):
        payload = {
            "status": 1,
            "product": {
                "code": BAMBA,
                "allergens_tags": ["en:peanuts"],
                "traces_tags": ["en:peanuts"],
            },
        }
        claims = off.to_claims(off.parse_product(payload), TODAY)
        assert len(claims) == 1
        assert claims[0].level is Level.CONTAINS

    def test_unrecognised_tags_are_reported_not_swallowed(self):
        payload = {
            "status": 1,
            "product": {"code": BAMBA, "allergens_tags": ["en:unobtainium"]},
        }
        product = off.parse_product(payload)
        assert product.allergen_ids == ()
        assert "unobtainium" in product.unmapped_tags
