"""בודק אילו אתרי יצרנים בכלל נגישים ומה יש בהם.

הבדיקה אמפירית ולא מבוססת הנחות. לכל קבוצה במרשם היא בודקת שלושה
דברים: האם האתר עונה, האם יש בו סימנים למידע אלרגנים, והאם יש בו
מבנה שאפשר לגזור ממנו ברקוד.

התוצאה קובעת לאיזה יצרנים כדאי לבנות מתאם. אתר שאינו עונה או שאין בו
אלרגנים אינו שווה עבודה, ועדיף לדעת את זה לפני שכותבים מתאם ולא אחרי.

    python -m allergen_pipeline.probe_manufacturers
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path

import httpx

from .catalog import manufacturers

DEFAULT_OUTPUT = Path("data/manufacturer_probe.json")

BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,"
        "image/avif,image/webp,*/*;q=0.8"
    ),
    "Accept-Language": "he-IL,he;q=0.9,en-US;q=0.8",
    "Upgrade-Insecure-Requests": "1",
}

REQUEST_TIMEOUT = 30.0
PAUSE_SECONDS = 1.0

# סימנים לכך שהאתר עוסק במידע אלרגנים ברמת מוצר.
_ALLERGEN_MARKERS = ("אלרגן", "אלרגנים", "עלול להכיל", "מכיל אלרגנים")
_INGREDIENT_MARKERS = ("רשימת רכיבים", "רכיבים:", "מרכיבים")
_PRODUCT_MARKERS = ("מוצרים", "מוצרינו", "products", "המוצרים שלנו")

# ברקוד בן 13 ספרות שמתחיל ב-729 בכל מקום בדף או בכתובת נכס.
_BARCODE = re.compile(r"729\d{10}")


@dataclass
class ProbeResult:
    group_id: str
    name_he: str
    website: str | None
    status: int | None = None
    reachable: bool = False
    has_allergen_words: bool = False
    has_ingredient_words: bool = False
    has_product_section: bool = False
    barcode_in_page: bool = False
    page_bytes: int = 0
    error: str | None = None

    @property
    def worth_an_adapter(self) -> bool:
        """האם כדאי להשקיע במתאם ליצרן הזה."""
        return self.reachable and self.has_allergen_words


def probe(client: httpx.Client, group: manufacturers.ManufacturerGroup) -> ProbeResult:
    result = ProbeResult(
        group_id=group.id, name_he=group.name_he, website=group.website
    )
    if not group.website:
        result.error = "אין כתובת אתר במרשם"
        return result

    try:
        response = client.get(group.website)
        result.status = response.status_code
        result.page_bytes = len(response.content)
        if response.status_code != 200:
            result.error = f"HTTP {response.status_code}"
            return result

        text = response.text
        result.reachable = True
        result.has_allergen_words = any(m in text for m in _ALLERGEN_MARKERS)
        result.has_ingredient_words = any(m in text for m in _INGREDIENT_MARKERS)
        result.has_product_section = any(m in text for m in _PRODUCT_MARKERS)
        result.barcode_in_page = bool(_BARCODE.search(text))
    except Exception as error:  # noqa: BLE001 - אתר אחד לא מפיל את הבדיקה
        result.error = type(error).__name__
    return result


def main(argv: list[str] | None = None) -> int:
    arguments = _parse_arguments(argv)
    groups = [g for g in manufacturers.GROUPS if g.website]

    print(f"בודק {len(groups)} אתרי יצרנים.\n")
    results: list[ProbeResult] = []

    with httpx.Client(
        headers=BROWSER_HEADERS, timeout=REQUEST_TIMEOUT, follow_redirects=True
    ) as client:
        for group in groups:
            result = probe(client, group)
            results.append(result)
            print(f"{_format(result)}", flush=True)
            time.sleep(PAUSE_SECONDS)

    reachable = [r for r in results if r.reachable]
    promising = [r for r in results if r.worth_an_adapter]

    print(f"\nנגישים: {len(reachable)} מתוך {len(results)}")
    print(f"עם סימני אלרגנים בדף הבית: {len(promising)}")
    if promising:
        print("\nמועמדים למתאם:")
        for result in promising:
            print(f"  {result.name_he} — {result.website}")

    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(
        json.dumps([asdict(r) for r in results], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"\nהתוצאות נכתבו ל-{arguments.output}")
    return 0


def _format(result: ProbeResult) -> str:
    if result.error:
        return f"  {result.name_he:22s} {result.error}"
    marks = []
    if result.has_allergen_words:
        marks.append("אלרגנים")
    if result.has_ingredient_words:
        marks.append("רכיבים")
    if result.has_product_section:
        marks.append("מוצרים")
    if result.barcode_in_page:
        marks.append("ברקוד")
    detail = ", ".join(marks) if marks else "אין סימנים בדף הבית"
    return f"  {result.name_he:22s} HTTP {result.status}  {detail}"


def _parse_arguments(argv: list[str] | None) -> argparse.Namespace:
    argument_parser = argparse.ArgumentParser(prog="probe_manufacturers")
    argument_parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return argument_parser.parse_args(argv)


if __name__ == "__main__":
    raise SystemExit(main())
