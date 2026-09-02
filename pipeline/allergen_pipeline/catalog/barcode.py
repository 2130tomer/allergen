"""אימות ונרמול של ברקודים.

הברקוד הוא המזהה הקנוני היחיד של מוצר, ולכן כל מה שנכנס למאגר נבדק.
ברקוד פנימי של רשת אינו GTIN תקף ואינו מזהה מוצר מחוץ לאותה רשת, ולכן
הוא נפסל ולא נשמר כאילו היה ברקוד אמיתי.
"""

from __future__ import annotations

import re

_NON_DIGITS = re.compile(r"[^0-9]")

VALID_LENGTHS = (8, 12, 13, 14)

# טווח קידומות שמיועד לשימוש פנימי של קמעונאים ואינו מזהה מוצר גלובלי.
_INTERNAL_PREFIXES = ("2",)


def normalize(raw: str | None) -> str:
    """משאיר ספרות בלבד."""
    if not raw:
        return ""
    return _NON_DIGITS.sub("", raw)


def check_digit(digits: str) -> int:
    """ספרת הביקורת של GTIN לפי התקן."""
    body = digits[:-1] if len(digits) in VALID_LENGTHS else digits
    total = 0
    for index, char in enumerate(reversed(body)):
        weight = 3 if index % 2 == 0 else 1
        total += int(char) * weight
    return (10 - (total % 10)) % 10


def is_valid_gtin(raw: str | None) -> bool:
    """האם המחרוזת היא GTIN באורך תקין ועם ספרת ביקורת נכונה."""
    digits = normalize(raw)
    if len(digits) not in VALID_LENGTHS:
        return False
    return check_digit(digits) == int(digits[-1])


def is_internal(raw: str | None) -> bool:
    """ברקוד פנימי של רשת, שאינו מזהה מוצר מחוץ לאותה רשת."""
    digits = normalize(raw)
    if not digits:
        return True
    if len(digits) not in VALID_LENGTHS:
        return True
    return digits.startswith(_INTERNAL_PREFIXES)


def to_gtin13(raw: str | None) -> str:
    """מרחיב ברקוד קצר ל-13 ספרות כדי שכל המקורות יתלכדו על אותו מפתח."""
    digits = normalize(raw)
    if len(digits) == 14 and digits.startswith("0"):
        digits = digits[1:]
    if len(digits) == 12:
        digits = "0" + digits
    return digits


def is_usable(raw: str | None) -> bool:
    """האם הברקוד ראוי לשמש כמפתח קנוני במאגר."""
    return is_valid_gtin(raw) and not is_internal(raw)
