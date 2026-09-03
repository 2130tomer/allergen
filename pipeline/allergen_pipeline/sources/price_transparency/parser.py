"""קריאת קבצי שקיפות מחירים. ראו ADR-0001.

התקנות מחייבות מבנה, אבל כל רשת מממשת אותו אחרת: שמות תגיות שונים
באותיות שונות, עטיפות שונות לרשימת הפריטים, וקידודים שונים. הקורא כאן
סלחני בכוונה בשמות התגיות ומחמיר בכוונה בתוכן: פריט שאין לו ברקוד
תקין אינו נכנס לקטלוג.
"""

from __future__ import annotations

import gzip
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Iterator

from ...catalog import barcode as barcode_utils
from ...catalog.product import RetailerOffer
from ..base import RunResult, RunStats, check_run

# שמות תגיות אפשריים לכל שדה, כפי שהם מופיעים בפועל אצל הרשתות השונות.
_FIELD_ALIASES: dict[str, tuple[str, ...]] = {
    "barcode": ("itemcode", "item_code", "barcode"),
    "name": ("itemname", "item_name", "itemnm", "productname"),
    # שופרסל כותבת ManufactureName ולא ManufacturerName. ההבדל נראה זניח
    # ועלה בהרצה הראשונה על קובץ אמיתי כשם יצרן ריק בכל השורות.
    "manufacturer": (
        "manufacturername",
        "manufacturename",
        "manufacturer_name",
        "manufacturername1",
        "manufactureitemdescription",
        "manufacturedescription",
    ),
    "quantity": ("quantity", "qty"),
    "unit": ("unitqty", "unitofmeasure", "unitmeasure"),
    "item_type": ("itemtype", "item_type"),
    "internal_code": ("iteminternalcode", "internalcode"),
    "update_date": (
        "priceupdatedate",
        "priceupdatetime",
        "price_update_date",
        "updatedate",
    ),
}

_ITEM_TAGS = ("item", "product", "line")

# ItemType 1 = פריט עם ברקוד יצרן. 0 = פריט שקיל או פנימי לרשת.
_BARCODED_ITEM_TYPE = "1"


@dataclass(frozen=True)
class ParsedFile:
    retailer_id: str
    store_id: str | None
    offers: list[RetailerOffer]
    skipped_invalid_barcode: int = 0
    skipped_weighted: int = 0


def _localname(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].strip().lower()


def _read_fields(element: ET.Element) -> dict[str, str]:
    values: dict[str, str] = {}
    for child in element:
        name = _localname(child.tag)
        text = (child.text or "").strip()
        if text:
            values[name] = text
    return values


"""ערכי מציין-מקום שרשתות כותבות במקום להשאיר שדה ריק.

רמי לוי כותבת את המחרוזת "לא ידוע" בשדות היצרן, ארץ הייצור ויחידת
המידה. בלי הסינון הזה "לא ידוע" היה הופך לשם היצרן הנפוץ ביותר
בקטלוג ומוצג למשתמש ככזה.
"""
_PLACEHOLDERS = frozenset(
    {
        "לא ידוע",
        "לא רלוונטי",
        "אין",
        "-",
        "--",
        "---",
        "n/a",
        "na",
        "null",
        "none",
        "unknown",
        "0",
    }
)


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    if not stripped or stripped.lower() in _PLACEHOLDERS:
        return None
    return stripped


def _pick(values: dict[str, str], field: str, clean: bool = True) -> str | None:
    """הערך הראשון שקיים באחד מהאליאסים של השדה.

    ``clean=False`` נדרש לשדות דגל מספריים: ItemType שווה "0" הוא ערך
    תקף שמסמן פריט שקיל, ואסור שייבלע ברשימת מציין-המקום.
    """
    for alias in _FIELD_ALIASES[field]:
        if alias not in values:
            continue
        value = values[alias]
        if not clean:
            return value.strip() or None
        cleaned = _clean(value)
        if cleaned is not None:
            return cleaned
    return None


def _parse_date(raw: str | None) -> date | None:
    """כל צורות התאריך שנצפו אצל הרשתות, כולל ISO עם T של שופרסל."""
    if not raw:
        return None
    text = raw.strip()
    for pattern in (
        # רמי לוי מוסיפה אלפיות שנייה, שופרסל לא.
        "%Y-%m-%dT%H:%M:%S.%f",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d",
        "%Y%m%d%H%M%S",
        "%Y%m%d",
    ):
        try:
            return datetime.strptime(text, pattern).date()
        except ValueError:
            continue
    return None


def _iter_items(root: ET.Element) -> Iterator[ET.Element]:
    for element in root.iter():
        if _localname(element.tag) in _ITEM_TAGS and len(element):
            yield element


def _read_bytes(path: Path) -> bytes:
    raw = path.read_bytes()
    if raw[:2] == b"\x1f\x8b":
        return gzip.decompress(raw)
    return raw


def parse_bytes(
    data: bytes,
    retailer_id: str,
    observed_on: date | None = None,
) -> ParsedFile:
    """קורא קובץ מחירים אחד והופך אותו להצעות רשת."""
    root = ET.fromstring(data.decode("utf-8-sig", errors="replace"))
    header = _read_fields(root)
    store_id = header.get("storeid") or header.get("store_id")

    offers: list[RetailerOffer] = []
    skipped_barcode = 0
    skipped_weighted = 0

    for element in _iter_items(root):
        values = _read_fields(element)
        raw_barcode = _pick(values, "barcode")
        name = _pick(values, "name")
        if not raw_barcode or not name:
            continue

        item_type = _pick(values, "item_type", clean=False)
        if item_type is not None and item_type.strip() != _BARCODED_ITEM_TYPE:
            skipped_weighted += 1
            continue

        if not barcode_utils.is_usable(raw_barcode):
            skipped_barcode += 1
            continue

        offers.append(
            RetailerOffer(
                retailer_id=retailer_id,
                barcode=barcode_utils.to_gtin13(raw_barcode),
                raw_name=name,
                manufacturer=_pick(values, "manufacturer"),
                quantity=_pick(values, "quantity"),
                unit=_pick(values, "unit"),
                retailer_sku=_pick(values, "internal_code"),
                observed_on=_parse_date(_pick(values, "update_date")) or observed_on,
            )
        )

    return ParsedFile(
        retailer_id=retailer_id,
        store_id=store_id,
        offers=offers,
        skipped_invalid_barcode=skipped_barcode,
        skipped_weighted=skipped_weighted,
    )


def parse_file(
    path: Path,
    retailer_id: str,
    observed_on: date | None = None,
) -> ParsedFile:
    return parse_bytes(_read_bytes(path), retailer_id, observed_on)


def parse_directory(
    directory: Path,
    retailer_id: str,
    previous_rows: int | None = None,
    observed_on: date | None = None,
) -> RunResult[RetailerOffer]:
    """קורא את כל קבצי המחירים של רשת אחת ומריץ בדיקת שפיות.

    בדיקה שנכשלת מסמנת את התוצאה כלא מאושרת, והצינור לא יכתוב אותה על
    נתונים קיימים.
    """
    started = datetime.now()
    offers: list[RetailerOffer] = []
    missing_required = 0

    for path in sorted(directory.glob("*")):
        if path.is_dir():
            continue
        parsed = parse_file(path, retailer_id, observed_on)
        offers.extend(parsed.offers)
        missing_required += parsed.skipped_invalid_barcode

    stats = RunStats(
        adapter_id=f"price_transparency:{retailer_id}",
        rows=len(offers) + missing_required,
        started_at=started,
        finished_at=datetime.now(),
        missing_required=missing_required,
    )

    result: RunResult[RetailerOffer] = RunResult(
        adapter_id=stats.adapter_id, items=offers, stats=stats
    )
    try:
        check_run(stats, previous_rows=previous_rows)
    except Exception as exc:  # noqa: BLE001 - נשמר כסיבת דחייה ולא מפיל את הריצה
        result.rejection_reason = str(exc)
        return result

    result.accepted = True
    return result
