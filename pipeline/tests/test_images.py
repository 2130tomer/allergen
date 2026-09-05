"""חיבור תמונות: סדר העדיפות בין המקורות, ומה שאסור להיכנס.

הבדיקות נשענות על מבנה המטמונים האמיתי, ולכן שינוי בשמות השדות שם
ישבור אותן במקום להשתיק את התמונות בלי שאיש ישים לב.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from allergen_pipeline.catalog import images
from allergen_pipeline.catalog.product import Product, ProductImage

TODAY = date(2026, 9, 5)


def write(path: Path, payload: dict) -> Path:
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


@pytest.fixture
def manufacturer_file(tmp_path: Path) -> Path:
    return write(
        tmp_path / "manufacturer.json",
        {
            "7290001302279": {
                "barcode": "7290001302279",
                "image_url": "https://osem.example/bamba.jpg",
            },
            "7290000066134": {"barcode": "7290000066134", "image_url": None},
        },
    )


@pytest.fixture
def off_file(tmp_path: Path) -> Path:
    return write(
        tmp_path / "off.json",
        {
            "7290001302279": {"image_front_url": "https://off.example/bamba.jpg"},
            "7290000066134": {"image_front_url": "https://off.example/bisli.jpg"},
            "7290000000001": {},
        },
    )


class TestSourcePrecedence:
    def test_the_manufacturer_image_wins(self, manufacturer_file, off_file):
        found = images.collect(manufacturer_file, off_file, TODAY)
        assert found["7290001302279"].url == "https://osem.example/bamba.jpg"
        assert found["7290001302279"].source_name == images.MANUFACTURER_SOURCE

    def test_off_fills_in_where_the_manufacturer_is_silent(
        self, manufacturer_file, off_file
    ):
        """ליצרן יש רשומה לברקוד הזה, אך בלי כתובת תמונה."""
        found = images.collect(manufacturer_file, off_file, TODAY)
        assert found["7290000066134"].url == "https://off.example/bisli.jpg"
        assert found["7290000066134"].source_name == images.OFF_SOURCE

    def test_a_record_without_an_image_yields_nothing(
        self, manufacturer_file, off_file
    ):
        found = images.collect(manufacturer_file, off_file, TODAY)
        assert "7290000000001" not in found

    def test_missing_cache_files_are_not_an_error(self, tmp_path):
        found = images.collect(tmp_path / "nope.json", tmp_path / "also-nope.json")
        assert found == {}


class TestAttaching:
    def product(self, barcode: str, image: ProductImage | None = None) -> Product:
        return Product(barcode=barcode, canonical_name="מוצר", image=image)

    def test_an_image_is_attached_to_a_matching_product(self):
        products = {"1": self.product("1")}
        image = ProductImage("https://x.example/a.jpg", "אתר היצרן", TODAY)
        updated, attached = images.attach(products, {"1": image})
        assert attached == 1
        assert updated["1"].image is image

    def test_an_image_without_a_matching_product_is_dropped(self):
        """שיוך לפי ברקוד בלבד. אין ניחוש לפי שם."""
        updated, attached = images.attach(
            {"1": self.product("1")},
            {"9": ProductImage("https://x.example/b.jpg", "אתר היצרן", TODAY)},
        )
        assert attached == 0
        assert updated["1"].image is None

    def test_an_existing_image_is_not_replaced(self):
        existing = ProductImage("https://keep.example/a.jpg", "אתר היצרן", TODAY)
        products = {"1": self.product("1", existing)}
        updated, attached = images.attach(
            products,
            {"1": ProductImage("https://other.example/b.jpg", "Open Food Facts", TODAY)},
        )
        assert attached == 0
        assert updated["1"].image is existing

    def test_attaching_does_not_mutate_the_input(self):
        products = {"1": self.product("1")}
        images.attach(
            products, {"1": ProductImage("https://x.example/a.jpg", "אתר היצרן", TODAY)}
        )
        assert products["1"].image is None
