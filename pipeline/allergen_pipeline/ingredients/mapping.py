"""זיהוי אלרגנים מתוך רשימת רכיבים.

שני תפקידים, שניהם קריטיים:

1. גילוי אלרגנים נסתרים שהיצרן לא הצהיר עליהם, כמו לציטין סויה במוצר
   שהצהרתו מזכירה רק חלב.
2. פירוק רשימת אלרגנים שטוחה של יצרן לרמות. ראו ADR-0004.

ההתאמה היא ברמת אסימונים ולא תת-מחרוזות, כי "חלבון" מכיל את "חלב"
ואינו מעיד עליו.

ביטויי ההרחקה משויכים לאלרגן שהם מנטרלים, ולא חלים על כולם. הניסיון
הקודם עם רשימת הרחקה גלובלית ייצר תקלה בכיוון המסוכן: "חמאת בוטנים"
נועד לנטרל את חלב, וניטרל בדרך גם את הבוטנים עצמם, כך שחמאת בוטנים
חזרה נקייה לגמרי. שיוך לאלרגן פותר גם את המקרה ההפוך: "חלב שקדים"
מנטרל את חלב ומשאיר את השקד, כפי שנכון.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from ..domain import allergens
from ..text import hebrew

DEFAULT_MAP_PATH = Path(__file__).parent / "data" / "ingredient_map.json"

_CompiledPhrases = list[tuple[str, tuple[str, ...]]]


@dataclass(frozen=True)
class IngredientMatch:
    """אלרגן שזוהה, והביטוי שגרם לזיהוי."""

    allergen_id: str
    matched_phrase: str
    position: int

    @property
    def explanation_he(self) -> str:
        label = allergens.get(self.allergen_id).label_he
        return f"{label} — זוהה מהרכיב {self.matched_phrase}"


def _compile(terms_by_key: dict[str, list[str]]) -> _CompiledPhrases:
    compiled: _CompiledPhrases = []
    for key, phrases in terms_by_key.items():
        for phrase in phrases:
            tokens = tuple(hebrew.tokenize(phrase))
            if tokens:
                compiled.append((key, tokens))
    # ביטויים ארוכים קודם, כדי שההתאמה הספציפית תנצח את הכללית.
    compiled.sort(key=lambda item: len(item[1]), reverse=True)
    return compiled


class IngredientAllergenMap:
    """טבלת המיפוי המתוחזקת ידנית, טעונה לזיכרון."""

    def __init__(
        self,
        allergen_terms: dict[str, list[str]],
        exclusions: dict[str, list[str]] | None = None,
    ) -> None:
        self._terms = _compile(allergen_terms)
        self._exclusions = _compile(exclusions or {})
        for allergen_id, _ in self._terms + self._exclusions:
            allergens.get(allergen_id)

    @classmethod
    def load(cls, path: Path | None = None) -> IngredientAllergenMap:
        raw = json.loads((path or DEFAULT_MAP_PATH).read_text(encoding="utf-8"))
        return cls(
            allergen_terms=raw["allergens"],
            exclusions=raw.get("exclusions") or {},
        )

    def match(self, ingredients_text: str | None) -> list[IngredientMatch]:
        """כל האלרגנים שזוהו ברשימת הרכיבים, עם הביטוי המזהה."""
        if not ingredients_text:
            return []

        tokens = hebrew.tokenize(ingredients_text)
        if not tokens:
            return []
        forms = [frozenset(hebrew.token_variants(token)) for token in tokens]

        blocked = self._blocked_positions(forms)
        return self._collect_matches(tokens, forms, blocked)

    def _blocked_positions(
        self, forms: list[frozenset[str]]
    ) -> dict[str, set[int]]:
        """מסמן לכל אלרגן אילו עמדות מנוטרלות עבורו בלבד."""
        blocked: dict[str, set[int]] = {}
        for allergen_id, phrase in self._exclusions:
            for start in _find_all(forms, phrase):
                blocked.setdefault(allergen_id, set()).update(
                    range(start, start + len(phrase))
                )
        return blocked

    def _collect_matches(
        self,
        tokens: list[str],
        forms: list[frozenset[str]],
        blocked: dict[str, set[int]],
    ) -> list[IngredientMatch]:
        consumed = [False] * len(forms)
        matches: list[IngredientMatch] = []

        for allergen_id, phrase in self._terms:
            span = len(phrase)
            for start in _find_all(forms, phrase):
                positions = range(start, start + span)
                if any(consumed[position] for position in positions):
                    continue
                if any(
                    position in blocked.get(allergen_id, ()) for position in positions
                ):
                    continue
                for position in positions:
                    consumed[position] = True
                matches.append(
                    IngredientMatch(
                        allergen_id=allergen_id,
                        matched_phrase=" ".join(tokens[start : start + span]),
                        position=start,
                    )
                )

        matches.sort(key=lambda match: match.position)
        return matches

    def allergen_ids(self, ingredients_text: str | None) -> set[str]:
        """רק מזהי האלרגנים, לשימוש בפירוק רשימה שטוחה."""
        return {match.allergen_id for match in self.match(ingredients_text)}


def _find_all(forms: list[frozenset[str]], phrase: tuple[str, ...]) -> list[int]:
    """כל העמדות שבהן רצף האסימונים מופיע."""
    span = len(phrase)
    if span == 0 or span > len(forms):
        return []
    return [
        start
        for start in range(len(forms) - span + 1)
        if all(phrase[offset] in forms[start + offset] for offset in range(span))
    ]
