"""מודל המוצר, והתנהגותו לאורך זמן.

המוצר קיים בקטלוג בלי קשר לזמינות מידע האלרגנים עליו. ראו ADR-0001.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import date

from ..text import hebrew
from . import departments, naming


@dataclass(frozen=True)
class RetailerOffer:
    """מוצר כפי שהוא מופיע בקובץ שקיפות מחירים של רשת אחת."""

    retailer_id: str
    barcode: str
    raw_name: str
    manufacturer: str | None = None
    quantity: str | None = None
    unit: str | None = None
    retailer_sku: str | None = None
    observed_on: date | None = None


@dataclass(frozen=True)
class ProductImage:
    url: str
    source_name: str
    fetched_on: date


@dataclass(frozen=True)
class Product:
    """מוצר קנוני אחד, מזוהה לפי ברקוד."""

    barcode: str
    canonical_name: str
    manufacturer: str | None = None
    department_id: str = departments.UNCLASSIFIED_ID
    aliases: tuple[str, ...] = ()
    quantity: str | None = None
    unit: str | None = None
    image: ProductImage | None = None
    first_seen_on: date | None = None
    last_seen_on: date | None = None
    is_active: bool = True
    # נדלק כשזוהה חשד למיחזור ברקוד. מקפיא את שיוך האלרגנים הישן.
    needs_review: bool = False
    review_reason: str | None = None
    retailer_ids: tuple[str, ...] = field(default_factory=tuple)

    @property
    def top_level_department_id(self) -> str:
        return departments.top_level_of(self.department_id)

    @property
    def search_text(self) -> str:
        """הטקסט שנכנס לעמודת החיפוש של תמונת המצב."""
        return hebrew.index_text(
            self.canonical_name, self.manufacturer, *self.aliases
        )


def build(
    barcode: str,
    offers: list[RetailerOffer],
    manufacturer_name: str | None = None,
    observed_on: date | None = None,
) -> Product:
    """מרכיב מוצר קנוני מהצעות של כמה רשתות."""
    if not offers:
        raise ValueError("לא ניתן לבנות מוצר בלי הצעות")

    names = [offer.raw_name for offer in offers]
    canonical = naming.canonical_name(names, manufacturer_name)
    manufacturer = manufacturer_name or _most_common_manufacturer(offers)
    dates = [offer.observed_on for offer in offers if offer.observed_on]
    seen_on = observed_on or (max(dates) if dates else None)

    return Product(
        barcode=barcode,
        canonical_name=canonical,
        manufacturer=manufacturer,
        department_id=departments.classify(canonical, manufacturer),
        aliases=naming.aliases(names, canonical),
        quantity=_first(offer.quantity for offer in offers),
        unit=_first(offer.unit for offer in offers),
        first_seen_on=seen_on,
        last_seen_on=seen_on,
        retailer_ids=tuple(dict.fromkeys(offer.retailer_id for offer in offers)),
    )


def merge_observation(existing: Product, incoming: Product) -> Product:
    """מעדכן מוצר קיים מריצה חדשה, ומזהה מיחזור ברקוד.

    שינוי דרסטי בשם לאותו ברקוד מסמן את המוצר לבדיקה במקום לדרוס בשקט
    את המידע הישן ולשייך אותו למוצר אחר.
    """
    if naming.looks_like_barcode_reuse(existing.canonical_name, incoming.canonical_name):
        return replace(
            incoming,
            first_seen_on=existing.first_seen_on,
            needs_review=True,
            review_reason=(
                f"שם המוצר לברקוד {existing.barcode} השתנה מ-"
                f"{existing.canonical_name} ל-{incoming.canonical_name}. "
                "חשד למיחזור ברקוד; המידע הישן מוקפא עד בדיקה."
            ),
        )

    merged_aliases = tuple(
        dict.fromkeys(existing.aliases + incoming.aliases + (existing.canonical_name,))
    )
    canonical_key = hebrew.normalize(incoming.canonical_name)
    merged_aliases = tuple(
        alias for alias in merged_aliases if hebrew.normalize(alias) != canonical_key
    )

    return replace(
        incoming,
        aliases=merged_aliases,
        image=incoming.image or existing.image,
        first_seen_on=existing.first_seen_on or incoming.first_seen_on,
        is_active=True,
        needs_review=existing.needs_review,
        review_reason=existing.review_reason,
        retailer_ids=tuple(
            dict.fromkeys(existing.retailer_ids + incoming.retailer_ids)
        ),
    )


def deactivate(product: Product, as_of: date) -> Product:
    """מוצר שנעלם מקבצי כל הרשתות נשאר במאגר ומסומן לא פעיל.

    מי שסורק פחית ישנה מהמזווה עדיין צריך לקבל תשובה.
    """
    return replace(product, is_active=False, last_seen_on=product.last_seen_on or as_of)


def _most_common_manufacturer(offers: list[RetailerOffer]) -> str | None:
    counts: dict[str, int] = {}
    for offer in offers:
        if offer.manufacturer and offer.manufacturer.strip():
            key = offer.manufacturer.strip()
            counts[key] = counts.get(key, 0) + 1
    if not counts:
        return None
    return max(counts, key=lambda name: (counts[name], -len(name)))


def _first(values) -> str | None:
    for value in values:
        if value:
            return value
    return None
