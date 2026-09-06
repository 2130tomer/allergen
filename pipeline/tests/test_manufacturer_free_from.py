"""הצהרת "ללא" של היצרן, והתנאי שמאפשר לה לצבוע ירוק.

ירוק הוא ההיפוך היחיד באפליקציה שאומר למשתמש משהו חיובי, ולכן הוא
הכיוון היחיד שבו טעות מסוכנת באמת. הכלל שנבחר: ירוק רק כשההצהרה
הגיעה מאתר היצרן של אותו מוצר.

שתי דרישות נפרדות, ושתיהן נבדקות כאן:

1. ההצהרה נקראה מדף היצרן, לא מטקסט קמעונאי. ADR-0008 חוסם את השני.
2. היצרן שבקטלוג הוא אותו יצרן שאת אתרו קראנו. בלי זה, דף של אסם היה
   יכול לצבוע בירוק מוצר של תנובה שקיבל בטעות אותו ברקוד.
"""

from __future__ import annotations

import json
from datetime import date

from allergen_pipeline.domain.claims import Level, Source
from allergen_pipeline.enrich import load_manufacturer_claims

BAMBA = "7290000066318"
OSEM_PAGE = "https://www.osem-nestle.co.il/brands/osem/gluten-free-cookies"


def _cache(tmp_path, name: str, page_url: str = OSEM_PAGE):
    path = tmp_path / "manufacturer_claims.json"
    path.write_text(
        json.dumps(
            {
                BAMBA: {
                    "barcode": BAMBA,
                    "name": name,
                    "page_url": page_url,
                    "observed_on": "2026-09-06",
                    "ingredients_text": "קמח אורז, סוכר, שמן",
                    "claims": [],
                }
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return path


def _absent(claims):
    return [c for c in claims.get(BAMBA, []) if c.level is Level.ABSENT]


class TestManufacturerDeclaredFreeFrom:
    def test_the_manufacturer_of_the_product_grants_green(self, tmp_path):
        path = _cache(tmp_path, "עוגיות ללא גלוטן אסם")
        claims = load_manufacturer_claims(path, {BAMBA: "אסם"})
        absent = _absent(claims)
        assert [c.allergen_id for c in absent] == ["gluten"]
        assert absent[0].source is Source.DECLARED_FREE_FROM

    def test_a_different_manufacturer_grants_nothing(self, tmp_path):
        """דף של אסם אינו מעיד על מוצר של תנובה.

        זה קורה כשברקוד ממוחזר או משויך בטעות, וזו בדיוק הנקודה שבה
        ירוק שגוי היה מגיע למסך.
        """
        path = _cache(tmp_path, "עוגיות ללא גלוטן אסם")
        assert _absent(load_manufacturer_claims(path, {BAMBA: "תנובה"})) == []

    def test_an_unknown_manufacturer_grants_nothing(self, tmp_path):
        """שם שאינו מזוהה לקבוצה אינו אימות. היעדר ידיעה אינו ראיה."""
        path = _cache(tmp_path, "עוגיות ללא גלוטן אסם")
        assert _absent(load_manufacturer_claims(path, {BAMBA: "יצרן כלשהו"})) == []
        assert _absent(load_manufacturer_claims(path, {BAMBA: None})) == []

    def test_a_page_outside_the_registry_grants_nothing(self, tmp_path):
        """אתר שאיננו יודעים של מי הוא אינו יכול לאמת דבר."""
        path = _cache(tmp_path, "עוגיות ללא גלוטן", page_url="https://example.test/x")
        assert _absent(load_manufacturer_claims(path, {BAMBA: "אסם"})) == []

    def test_without_the_catalog_no_green_is_emitted(self, tmp_path):
        """בלי הקטלוג אין את מי לאמת, ולכן אין ירוק. ברירת מחדל בטוחה."""
        path = _cache(tmp_path, "עוגיות ללא גלוטן אסם")
        assert _absent(load_manufacturer_claims(path)) == []

    def test_reduced_is_presence_and_never_green(self, tmp_path):
        """מוצר דל לקטוז מכיל לקטוז."""
        path = _cache(tmp_path, "מעדן דל לקטוז אסם")
        claims = load_manufacturer_claims(path, {BAMBA: "אסם"})
        assert _absent(claims) == []
        assert any(
            c.allergen_id == "lactose" and c.level is Level.CONTAINS
            for c in claims[BAMBA]
        )

    def test_existing_claims_are_kept(self, tmp_path):
        path = tmp_path / "manufacturer_claims.json"
        path.write_text(
            json.dumps(
                {
                    BAMBA: {
                        "barcode": BAMBA,
                        "name": "במבה אסם",
                        "page_url": OSEM_PAGE,
                        "observed_on": "2026-09-06",
                        "claims": [{"allergen_id": "peanuts", "level": "contains"}],
                    }
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        claims = load_manufacturer_claims(path, {BAMBA: "אסם"})
        assert any(
            c.allergen_id == "peanuts" and c.level is Level.CONTAINS
            for c in claims[BAMBA]
        )
