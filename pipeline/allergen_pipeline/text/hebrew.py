"""נרמול טקסט עברי לחיפוש.

החיפוש רץ על המכשיר מול תמונת מצב מקומית, ולכן הנרמול חייב להיות זהה
בצד האינדוקס בפייתון ובצד השאילתה באפליקציה. כל שינוי כאן מחייב שינוי
מקביל ב-app/src/text/hebrew.ts ובניית תמונת מצב מחדש.

הטיפול בתחיליות הוא תוספתי ולא הרסני: מהמילה נגזר גם הגזע בלי התחילית,
ושתי הצורות נכנסות לאינדקס. הסרה הרסנית הייתה הופכת "מלח" ל"לח".
"""

from __future__ import annotations

import re
import unicodedata

# סימני ניקוד וטעמים
_NIQQUD = re.compile(r"[\u0591-\u05C7]")

# גרש, גרשיים, מרכאות ואפוסטרופים בכל וריאציה
_QUOTES = re.compile(r"[\u05F3\u05F4'\"\u2018\u2019\u201C\u201D\u02BC`]")

# מקפים ומפרידים
_DASHES = re.compile(r"[\-\u2010\u2011\u2012\u2013\u2014\u2015_/\|]+")

_NON_WORD = re.compile(r"[^\w\u0590-\u05FF]+", re.UNICODE)
_WHITESPACE = re.compile(r"\s+")

# \u05E1\u05E4\u05E8\u05D5\u05EA \u05D3\u05D1\u05D5\u05E7\u05D5\u05EA \u05DC\u05D0\u05D5\u05EA\u05D9\u05D5\u05EA. \u05D1\u05E7\u05D1\u05E6\u05D9 \u05D4\u05E8\u05E9\u05EA\u05D5\u05EA \u05D6\u05D4 \u05E0\u05E4\u05D5\u05E5 \u05DE\u05D0\u05D5\u05D3: "100\u05D2", "32\u05D9\u05D7",
# "5\u05E1\u05DB\u05D9\u05E0\u05D9". \u05D1\u05DC\u05D9 \u05D4\u05E4\u05E8\u05D3\u05D4 \u05D4\u05D0\u05E1\u05D9\u05DE\u05D5\u05DF \u05DB\u05D5\u05DC\u05D5 \u05E9\u05D5\u05E0\u05D4 \u05DE\u05D4\u05DE\u05D9\u05DC\u05D4, \u05D5\u05D0\u05E3 \u05DB\u05DC\u05DC \u05D5\u05D7\u05D9\u05E4\u05D5\u05E9 \u05DC\u05D0
# \u05DE\u05D5\u05E6\u05D0\u05D9\u05DD \u05D0\u05D5\u05EA\u05D5.
_DIGIT_THEN_LETTER = re.compile(r"(\d)(?=[^\d\s])")
_LETTER_THEN_DIGIT = re.compile(r"([^\d\s])(?=\d)")

_FINAL_LETTERS = str.maketrans("ךםןףץ", "כמנפצ")

# תחיליות נפוצות. ארוכות קודם, כדי שהגזירה תנסה קודם את המפורשת יותר.
_PREFIXES: tuple[str, ...] = (
    "וכש",
    "ולכ",
    "כש",
    "לכ",
    "מה",
    "שה",
    "וה",
    "וב",
    "ול",
    "ומ",
    "וש",
    "ו",
    "ה",
    "ב",
    "ל",
    "מ",
    "ש",
    "כ",
)

# אורך הגזע המינימלי שנשאר אחרי גזירת תחילית.
MIN_STEM_LENGTH = 3

_BARCODE_CHARS = re.compile(r"[^0-9]")
MIN_BARCODE_DIGITS = 8
MAX_BARCODE_DIGITS = 14


def strip_niqqud(text: str) -> str:
    return _NIQQUD.sub("", unicodedata.normalize("NFC", text))


def normalize(text: str) -> str:
    """מביא טקסט לצורה קנונית להשוואה ולחיפוש."""
    if not text:
        return ""
    result = strip_niqqud(text)
    result = _QUOTES.sub("", result)
    result = _DASHES.sub(" ", result)
    result = _NON_WORD.sub(" ", result)
    result = _DIGIT_THEN_LETTER.sub(r"\1 ", result)
    result = _LETTER_THEN_DIGIT.sub(r"\1 ", result)
    result = result.translate(_FINAL_LETTERS)
    result = _WHITESPACE.sub(" ", result).strip()
    return result.lower()


def tokenize(text: str) -> list[str]:
    normalized = normalize(text)
    return normalized.split() if normalized else []


def strip_prefix(token: str) -> str | None:
    """גוזר תחילית אחת מהאסימון, אם נשאר גזע ארוך מספיק."""
    for prefix in _PREFIXES:
        if not token.startswith(prefix):
            continue
        stem = token[len(prefix) :]
        if len(stem) >= MIN_STEM_LENGTH:
            return stem
    return None


def token_variants(token: str) -> list[str]:
    """האסימון עצמו, ואחריו הגזע בלי תחילית אם קיים."""
    variants = [token]
    stem = strip_prefix(token)
    if stem and stem not in variants:
        variants.append(stem)
    return variants


def index_text(*parts: str | None) -> str:
    """בונה את הטקסט שנכנס לעמודת החיפוש מכמה שדות מקור."""
    seen: dict[str, None] = {}
    for part in parts:
        if not part:
            continue
        for token in tokenize(part):
            for variant in token_variants(token):
                seen.setdefault(variant, None)
    return " ".join(seen)


def normalize_barcode(text: str) -> str:
    return _BARCODE_CHARS.sub("", text or "")


def looks_like_barcode(text: str) -> bool:
    """האם השאילתה היא ברקוד ולא טקסט חופשי.

    מפריד בין שני מצבי החיפוש בשדה האחד. רק ספרות ומפרידים, ואורך
    בטווח של ברקודי מסחר.
    """
    if not text:
        return False
    stripped = text.strip()
    if not re.fullmatch(r"[0-9\s\-]+", stripped):
        return False
    digits = normalize_barcode(stripped)
    return MIN_BARCODE_DIGITS <= len(digits) <= MAX_BARCODE_DIGITS
