"""זיהוי הצהרות "ללא" מפורשות על האריזה.

הצהרת "ללא גלוטן" אינה היעדר מידע. היא טענה פוזיטיבית ומוסדרת שהיצרן
נושא באחריות עליה, ולכן היא הבסיס היחיד שבו האפליקציה מרשה לעצמה לומר
על מוצר שהוא אינו מכיל אלרגן. ראו ADR-0007.

שלוש הבחנות בנויות לתוך המודול, וכל אחת מהן נועדה למנוע טעות מסוכנת:

"דל" אינו "נטול". חלב דל לקטוז מכיל לקטוז, בכמות קטנה יותר. הוא נרשם
כמכיל, לא כנקי, ולעולם לא יקבל סימון ירוק. זו הסיבה שביטויי ההפחתה
מנוהלים ברשימה נפרדת ולא כווריאציה של ההצהרה.

"פרווה" אינו הצהרת אלרגן. זהו סימון כשרות, שאינו מבטיח היעדר עקבות
חלב ואינו נבדק במעבדה לצורך זה. הוא אינו מזכה בסימון ירוק.

הצהרה על מוצר אחד אינה חלה על שכניו באריזה. הזיהוי רץ על שם המוצר
ועל טקסט התווית שלו בלבד.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from ..domain import allergens
from ..text import hebrew

DEFAULT_PATH = Path(__file__).parent / "data" / "free_from_map.json"


@dataclass(frozen=True)
class FreeFromClaim:
    """הצהרת היעדר שזוהתה, והביטוי שהעיד עליה."""

    allergen_id: str
    matched_phrase: str

    @property
    def explanation_he(self) -> str:
        label = allergens.get(self.allergen_id).label_he
        return f"{label} — הצהרת {self.matched_phrase} על האריזה"


@dataclass(frozen=True)
class ReducedClaim:
    """הצהרת הפחתה. מעידה על נוכחות, לא על היעדר."""

    allergen_id: str
    matched_phrase: str

    @property
    def explanation_he(self) -> str:
        label = allergens.get(self.allergen_id).label_he
        return f"{label} — המוצר מוצהר כ{self.matched_phrase}, כלומר עדיין מכיל"


def _compile(raw: dict[str, list[str]]) -> list[tuple[str, tuple[str, ...]]]:
    compiled = []
    for allergen_id, phrases in raw.items():
        allergens.get(allergen_id)
        for phrase in phrases:
            tokens = tuple(hebrew.tokenize(phrase))
            if tokens:
                compiled.append((allergen_id, tokens))
    compiled.sort(key=lambda item: len(item[1]), reverse=True)
    return compiled


class FreeFromDetector:
    """מזהה הצהרות "ללא" ו"דל" בטקסט חופשי."""

    def __init__(
        self,
        free_from: dict[str, list[str]],
        reduced: dict[str, list[str]] | None = None,
    ) -> None:
        self._free_from = _compile(free_from)
        self._reduced = _compile(reduced or {})

    @classmethod
    def load(cls, path: Path | None = None) -> FreeFromDetector:
        raw = json.loads((path or DEFAULT_PATH).read_text(encoding="utf-8"))
        return cls(
            free_from=raw["free_from"],
            reduced=raw.get("reduced") or {},
        )

    def detect(self, *texts: str | None) -> tuple[list[FreeFromClaim], list[ReducedClaim]]:
        """ההצהרות שנמצאו בטקסטים, מופרדות להיעדר ולהפחתה.

        ביטוי הפחתה גובר על ביטוי היעדר לאותו אלרגן. "דל לקטוז" מכיל
        בתוכו את האסימון "לקטוז", ובלי הכרעה מפורשת לטובת המחמיר היה
        מוצר דל-לקטוז עלול להיצבע כנקי ממנו.
        """
        joined = " ".join(text for text in texts if text)
        if not joined.strip():
            return [], []

        tokens = hebrew.tokenize(joined)
        if not tokens:
            return [], []
        forms = [frozenset(hebrew.token_variants(token)) for token in tokens]

        reduced = [
            ReducedClaim(allergen_id, " ".join(tokens[start : start + len(phrase)]))
            for allergen_id, phrase in self._reduced
            for start in _find_all(forms, phrase)
        ]
        reduced_ids = {claim.allergen_id for claim in reduced}

        free_from = [
            FreeFromClaim(allergen_id, " ".join(tokens[start : start + len(phrase)]))
            for allergen_id, phrase in self._free_from
            for start in _find_all(forms, phrase)
            if allergen_id not in reduced_ids
        ]
        return _dedupe(free_from), _dedupe(reduced)


def _dedupe(claims: list):
    seen: set[str] = set()
    unique = []
    for claim in claims:
        if claim.allergen_id not in seen:
            seen.add(claim.allergen_id)
            unique.append(claim)
    return unique


def _find_all(forms: list[frozenset[str]], phrase: tuple[str, ...]) -> list[int]:
    span = len(phrase)
    if span == 0 or span > len(forms):
        return []
    return [
        start
        for start in range(len(forms) - span + 1)
        if all(phrase[offset] in forms[start + offset] for offset in range(span))
    ]
