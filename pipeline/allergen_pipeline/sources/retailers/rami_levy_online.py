"""מתאם רמי לוי אונליין.

הקמעונאי השני, אחרי ששופרסל מוצתה. שני התנאים שבגללם נבחר קמעונאי
מלכתחילה מתקיימים גם כאן: כתובת אחת לפי ברקוד, בלי בעיית מנייה, ושני
שדות נפרדים למכיל ולעלול להכיל.

ההבדל משופרסל הוא שהאלרגנים מגיעים כקודים מספריים ולא כטקסט. הקודים
מפוענחים דרך מילון שנשמר בגיט, ולא דרך ניחוש. הניסיון לפענח אותם
בקורלציה מול הסנאפשוט ייחס את 6843 לאגוזי קשיו, ובפועל 6843 הוא "אין" —
כלומר ניחוש היה מייצר אלרגן יש מאין. ראו rami_levy_allergen_codes.json.

הרמה נקבעת לפי השדה שבו הקוד הופיע, ולא לפי ניסוח התווית. קוד שכתוב בו
"עקבות של בוטנים" והופיע בשדה מכיל נרשם כמכיל: המערכת מחמירה, ואינה
מקלה על סמך ניסוח.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

API_URL = "https://www.rami-levy.co.il/api/catalog"
PRODUCT_URL = "https://www.rami-levy.co.il/he/online/search?q={barcode}"

DEFAULT_CODE_MAP_PATH = Path(__file__).parent / "data" / "rami_levy_code_map.json"

CONTAINS_FIELD = "Allergen_Type_Code_and_Containment"
MAY_CONTAIN_FIELD = "Allergen_Type_Code_and_Containment_May_Contain"


@dataclass(frozen=True)
class RamiLevyProduct:
    barcode: str
    name: str | None
    brand: str | None
    ingredients_text: str | None
    contains_ids: tuple[str, ...]
    may_contain_ids: tuple[str, ...]
    page_url: str
    #: קודים שהמקור החזיר ואינם במילון. מדווחים ואינם נבלעים.
    unknown_codes: tuple[str, ...] = ()

    @property
    def has_allergen_fields(self) -> bool:
        return bool(self.contains_ids or self.may_contain_ids)


class RamiLevyCodeMap:
    """מילון הקודים, טעון לזיכרון.

    codes ממפה קוד לרשימת אלרגנים, ו-ignored מחזיק קודים שהוכרעו במפורש
    כלא־אלרגן, עם הסיבה. קוד שאינו בשניהם הוא קוד חדש שהמקור הוסיף, והוא
    מדווח כדי שההחלטה עליו תהיה מודעת ולא שקטה.
    """

    def __init__(self, codes: dict[str, list[str]], ignored: dict[str, str]) -> None:
        self._codes = {str(key): tuple(value) for key, value in codes.items()}
        self._ignored = {str(key) for key in ignored}

    @classmethod
    def load(cls, path: Path | None = None) -> RamiLevyCodeMap:
        raw = json.loads((path or DEFAULT_CODE_MAP_PATH).read_text(encoding="utf-8"))
        return cls(codes=raw["codes"], ignored=raw.get("ignored") or {})

    def resolve(self, codes) -> tuple[set[str], list[str]]:
        """מחזיר את האלרגנים שזוהו, ואת הקודים שאינם מוכרים."""
        found: set[str] = set()
        unknown: list[str] = []
        for code in codes or ():
            key = str(code)
            if key in self._codes:
                found.update(self._codes[key])
            elif key not in self._ignored:
                unknown.append(key)
        return found, unknown


def parse_product(payload: dict, requested_barcode: str) -> RamiLevyProduct | None:
    """הופך תשובת catalog אחת למוצר. מחזיר None כשהמוצר לא נמצא.

    השיוך הוא לפי ברקוד ולפי ברקוד בלבד. תשובה שמחזירה מוצר אחר מזו
    שנתבקשה נדחית, כי הצגת אלרגנים של מוצר שכן היא בדיוק הטעות שאין
    לה תיקון.
    """
    items = (payload or {}).get("data") or []
    if not items:
        return None

    requested = str(requested_barcode).strip()
    item = None
    for candidate in items:
        if str(candidate.get("barcode") or "").strip() == requested:
            item = candidate
            break
    if item is None:
        return None

    gs = item.get("gs") or {}
    code_map = _CODE_MAP_SINGLETON()
    contains, unknown_contains = code_map.resolve(gs.get(CONTAINS_FIELD))
    may_contain, unknown_may = code_map.resolve(gs.get(MAY_CONTAIN_FIELD))

    # אלרגן שהוצהר בשתי הרמות נשאר במחמירה.
    may_contain -= contains

    ingredients = (gs.get("Ingredient_Sequence_and_Name") or "").strip() or None

    return RamiLevyProduct(
        barcode=requested,
        name=item.get("name") or gs.get("internal_product_description"),
        brand=gs.get("BrandName"),
        ingredients_text=ingredients,
        contains_ids=tuple(sorted(contains)),
        may_contain_ids=tuple(sorted(may_contain)),
        page_url=PRODUCT_URL.format(barcode=requested),
        unknown_codes=tuple(dict.fromkeys(unknown_contains + unknown_may)),
    )


_CACHED_MAP: RamiLevyCodeMap | None = None


def _CODE_MAP_SINGLETON() -> RamiLevyCodeMap:
    global _CACHED_MAP
    if _CACHED_MAP is None:
        _CACHED_MAP = RamiLevyCodeMap.load()
    return _CACHED_MAP


def request_body(barcode: str, store: int = 331) -> dict:
    """גוף הבקשה. store הוא סניף; האלרגנים אינם תלויים בו."""
    return {"q": str(barcode), "store": store}
