"""זיהוי אלרגנים מתוך רשימת רכיבים.

שני תפקידים, שניהם קריטיים:

1. גילוי אלרגנים נסתרים שהיצרן לא הצהיר עליהם, כמו לציטין סויה במוצר
   שהצהרתו מזכירה רק חלב.
2. פירוק רשימת אלרגנים שטוחה של יצרן לרמות. ראו ADR-0004.

ההתאמה היא ברמת אסימונים ולא תת-מחרוזות, כי "חלבון" מכיל את "חלב"
ואינו מעיד עליו. ביטויי הרחקה כמו "חלב קוקוס" נצרכים ראשונים, ולכן
מנטרלים את ההתאמה הכללית יותר.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from ..domain import allergens
from ..text import hebrew

DEFAULT_MAP_PATH = Path(__file__).parent / "data" / "ingredient_map.json"


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


def _phrase_tokens(phrase: str) -> tuple[str, ...]:
    return tuple(hebrew.tokenize(phrase))


def _token_forms(token: str) -> frozenset[str]:
    return frozenset(hebrew.token_variants(token))


class IngredientAllergenMap:
    """טבלת המיפוי המתוחזקת ידנית, טעונה לזיכרון."""

    def __init__(
        self,
        allergen_terms: dict[str, list[str]],
        exclusions: list[str] | None = None,
    ) -> None:
        self._exclusions = self._compile(
            {"__excluded__": exclusions or []}
        )
        compiled = self._compile(allergen_terms)
        for allergen_id, _ in compiled:
            allergens.get(allergen_id)
        self._terms = compiled

    @staticmethod
    def _compile(
        terms_by_key: dict[str, list[str]],
    ) -> list[tuple[str, tuple[str, ...]]]:
        compiled: list[tuple[str, tuple[str, ...]]] = []
        for key, phrases in terms_by_key.items():
            for phrase in phrases:
                tokens = _phrase_tokens(phrase)
                if tokens:
                    compiled.append((key, tokens))
        # ביטויים ארוכים קודם, כדי שההתאמה הספציפית תנצח את הכללית
        compiled.sort(key=lambda item: len(item[1]), reverse=True)
        return compiled

    @classmethod
    def load(cls, path: Path | None = None) -> IngredientAllergenMap:
        raw = json.loads((path or DEFAULT_MAP_PATH).read_text(encoding="utf-8"))
        return cls(
            allergen_terms=raw["allergens"],
            exclusions=raw.get("exclusions", []),
        )

    def match(self, ingredients_text: str | None) -> list[IngredientMatch]:
        """כל האלרגנים שזוהו ברשימת הרכיבים, עם הביטוי המזהה."""
        if not ingredients_text:
            return []

        tokens = hebrew.tokenize(ingredients_text)
        if not tokens:
            return []
        forms = [_token_forms(token) for token in tokens]
        consumed = [False] * len(tokens)

        self._consume(forms, consumed, self._exclusions, collect=None)

        matches: list[IngredientMatch] = []
        self._consume(forms, consumed, self._terms, collect=matches, tokens=tokens)
        matches.sort(key=lambda m: m.position)
        return matches

    @staticmethod
    def _consume(
        forms: list[frozenset[str]],
        consumed: list[bool],
        compiled: list[tuple[str, tuple[str, ...]]],
        collect: list[IngredientMatch] | None,
        tokens: list[str] | None = None,
    ) -> None:
        for key, phrase in compiled:
            span = len(phrase)
            for start in range(len(forms) - span + 1):
                if any(consumed[start : start + span]):
                    continue
                if all(
                    phrase[offset] in forms[start + offset] for offset in range(span)
                ):
                    for offset in range(span):
                        consumed[start + offset] = True
                    if collect is not None:
                        matched_text = (
                            " ".join(tokens[start : start + span])
                            if tokens
                            else " ".join(phrase)
                        )
                        collect.append(
                            IngredientMatch(
                                allergen_id=key,
                                matched_phrase=matched_text,
                                position=start,
                            )
                        )

    def allergen_ids(self, ingredients_text: str | None) -> set[str]:
        """רק מזהי האלרגנים, לשימוש בפירוק רשימה שטוחה."""
        return {match.allergen_id for match in self.match(ingredients_text)}
