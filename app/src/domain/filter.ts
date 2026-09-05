/** Exclusion policies shared with Python. May-contain exclusions also exclude contains. */

import { expandSelection, labelOf } from './allergens';

export type Level = 'contains' | 'may_contain' | 'absent' | 'unknown';

/**
 * absent אינו "לא הוזכר" אלא "הוצהר במפורש שאינו קיים".
 *
 * ההבחנה מהותית ומגובה במודל: רק הצהרת יצרן או הצהרת "ללא" מודפסת על
 * האריזה מייצרות את המצב הזה, ולעולם לא היעדר אזכור. ראו ADR-0002.
 */
export const LEVEL_LABEL: Record<Level, string> = {
  contains: 'מכיל',
  may_contain: 'עלול להכיל',
  absent: 'הוצהר "ללא"',
  unknown: 'אין מידע',
};

export type Visibility = 'visible' | 'hidden' | 'unknown';

/** מצב האלרגנים של מוצר אחד, כפי שנקרא מתמונת המצב. */
export type AllergenLevels = Readonly<Record<string, Level>>;

export interface FilterSelection {
  /** רמת הסינון הראשונה. מוצר שמכיל אחד מאלה מוסתר. */
  readonly contains: ReadonlySet<string>;
  /** רמת הסינון השנייה. מוצר שעלול להכיל אחד מאלה מוסתר. */
  readonly mayContain: ReadonlySet<string>;
}

export const EMPTY_SELECTION: FilterSelection = {
  contains: new Set(),
  mayContain: new Set(),
};

export interface FilterOutcome {
  visibility: Visibility;
  matchedAllergenIds: string[];
  unknownAllergenIds: string[];
}

export function levelOf(levels: AllergenLevels, allergenId: string): Level {
  return levels[allergenId] ?? 'unknown';
}

export function isEmptySelection(selection: FilterSelection): boolean {
  return selection.contains.size === 0 && selection.mayContain.size === 0;
}

export function selectedIds(selection: FilterSelection): Set<string> {
  return new Set([...selection.contains, ...selection.mayContain]);
}

/** Explain legacy may-only preferences, which now exclude both positive levels. */
export function gapWarnings(selection: FilterSelection): string[] {
  const onlyMayContain = [...selection.mayContain].filter(
    (id) => !selection.contains.has(id),
  );
  return onlyMayContain
    .sort()
    .map(
      (id) =>
        `סימנת ${labelOf(id)} רק ברשימת עלול להכיל. הסינון כולל גם מוצרים שמכילים ${labelOf(id)}.`,
    );
}

/** האם יש מידע כלשהו על האלרגן שנבחר, או על אחד מתת-סוגיו. */
function selectionIsKnown(levels: AllergenLevels, allergenId: string): boolean {
  if (levelOf(levels, allergenId) !== 'unknown') return true;
  const children = [...expandSelection([allergenId])].filter((id) => id !== allergenId);
  return children.length > 0 && (
    children.some((id) => ['contains', 'may_contain'].includes(levelOf(levels, id))) ||
    children.every((id) => levelOf(levels, id) === 'absent')
  );
}

/** מכריע אם מוצר מוצג, מוסתר, או נופל לסעיף אין מידע. */
export function applyFilter(
  selection: FilterSelection,
  levels: AllergenLevels,
): FilterOutcome {
  if (isEmptySelection(selection)) {
    return { visibility: 'visible', matchedAllergenIds: [], unknownAllergenIds: [] };
  }

  const matched: string[] = [];
  for (const id of [...expandSelection(selectedIds(selection))].sort()) {
    if (levelOf(levels, id) === 'contains') matched.push(id);
  }
  for (const id of [...expandSelection(selection.mayContain)].sort()) {
    if (levelOf(levels, id) === 'may_contain') matched.push(id);
  }

  if (matched.length > 0) {
    return {
      visibility: 'hidden',
      matchedAllergenIds: [...new Set(matched)],
      unknownAllergenIds: [],
    };
  }

  const unknown = [...selectedIds(selection)]
    .sort()
    .filter((id) => !selectionIsKnown(levels, id));

  if (unknown.length > 0) {
    return { visibility: 'unknown', matchedAllergenIds: [], unknownAllergenIds: unknown };
  }

  return { visibility: 'visible', matchedAllergenIds: [], unknownAllergenIds: [] };
}

export function toggle(set: ReadonlySet<string>, id: string): Set<string> {
  const next = new Set(set);
  if (next.has(id)) {
    next.delete(id);
  } else {
    next.add(id);
  }
  return next;
}

/** צורת ההחסנה המקומית. אין פרופילים; זו רק זכירת הבחירה האחרונה. */
export interface StoredSelection {
  contains: string[];
  mayContain: string[];
}

export function serialize(selection: FilterSelection): StoredSelection {
  return {
    contains: [...selection.contains].sort(),
    mayContain: [...selection.mayContain].sort(),
  };
}

export function deserialize(stored: Partial<StoredSelection> | null): FilterSelection {
  return {
    contains: new Set(stored?.contains ?? []),
    mayContain: new Set(stored?.mayContain ?? []),
  };
}

export type FilterPolicy = 'none' | 'contains' | 'contains_and_may';
export function policyOf(selection: FilterSelection, id: string): FilterPolicy {
  return selection.mayContain.has(id) ? 'contains_and_may' : selection.contains.has(id) ? 'contains' : 'none';
}
export function withPolicy(selection: FilterSelection, id: string, policy: FilterPolicy): FilterSelection {
  const contains = new Set(selection.contains);
  const mayContain = new Set(selection.mayContain);
  contains.delete(id);
  mayContain.delete(id);
  if (policy !== 'none') contains.add(id);
  if (policy === 'contains_and_may') mayContain.add(id);
  return { contains, mayContain };
}
