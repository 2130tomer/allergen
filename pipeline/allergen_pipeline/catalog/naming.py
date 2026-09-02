"""בחירת השם הקנוני של מוצר, ואיתור ברקוד ממוחזר.

אותו ברקוד מופיע בקבצים של כמה רשתות עם שמות שונים. השם הקנוני הוא
השם הנפוץ ביותר אחרי נרמול, ושם רשמי מהיצרן גובר עליו כשקיים. כל שאר
השמות נשמרים כשמות נרדפים ונכנסים לאינדקס החיפוש בלבד.
"""

from __future__ import annotations

from collections import Counter

from ..text import hebrew

# מתחת לדמיון הזה בין השם הישן לחדש, אותו ברקוד נחשב למוצר אחר.
BARCODE_REUSE_SIMILARITY_THRESHOLD = 0.2


def canonical_name(
    retailer_names: list[str],
    manufacturer_name: str | None = None,
) -> str:
    """השם שבו המוצר יוצג."""
    if manufacturer_name and manufacturer_name.strip():
        return manufacturer_name.strip()

    cleaned = [name.strip() for name in retailer_names if name and name.strip()]
    if not cleaned:
        return ""

    # מקבצים לפי הצורה המנורמלת, ומציגים את הכתיב הנפוץ ביותר בתוך הקבוצה.
    by_normalized: dict[str, Counter[str]] = {}
    for name in cleaned:
        key = hebrew.normalize(name)
        by_normalized.setdefault(key, Counter())[name] += 1

    # השם הנפוץ ביותר מנצח. בתיקו מנצח השם הארוך יותר, כי הוא בדרך כלל
    # זה שכולל את שם היצרן ואת הגודל.
    best_key = max(
        by_normalized,
        key=lambda key: (sum(by_normalized[key].values()), len(key)),
    )
    return by_normalized[best_key].most_common(1)[0][0]


def aliases(retailer_names: list[str], canonical: str) -> tuple[str, ...]:
    """כל שם אחר שרשת נתנה למוצר. אינו מוצג, רק נכנס לאינדקס."""
    canonical_key = hebrew.normalize(canonical)
    seen: dict[str, None] = {}
    for name in retailer_names:
        if not name or not name.strip():
            continue
        stripped = name.strip()
        if hebrew.normalize(stripped) == canonical_key:
            continue
        seen.setdefault(stripped, None)
    return tuple(seen)


def name_similarity(first: str, second: str) -> float:
    """דמיון ז'קרד בין אסימוני שני שמות, אחרי נרמול."""
    first_tokens = set(hebrew.tokenize(first))
    second_tokens = set(hebrew.tokenize(second))
    if not first_tokens or not second_tokens:
        return 0.0
    intersection = first_tokens & second_tokens
    union = first_tokens | second_tokens
    return len(intersection) / len(union)


def looks_like_barcode_reuse(previous_name: str, new_name: str) -> bool:
    """האם שינוי השם מעיד שהברקוד הוקצה מחדש למוצר אחר.

    GS1 ממחזרת ברקודים של מוצרים שירדו מהמדף. שינוי דרסטי בשם לאותו
    ברקוד הוא הסימן הזמין היחיד. במקרה כזה המידע הישן מוקפא ומסומן
    לבדיקה, במקום להיות מיוחס בטעות למוצר החדש.
    """
    if not previous_name or not new_name:
        return False
    return name_similarity(previous_name, new_name) < BARCODE_REUSE_SIMILARITY_THRESHOLD
