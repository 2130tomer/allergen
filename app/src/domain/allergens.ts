/**
 * הרשימה הסגורה של האלרגנים והיררכיית אגוזי העץ.
 *
 * מראה של pipeline/allergen_pipeline/domain/allergens.py. הרשימה נטענת
 * גם מתמונת המצב, אך מוגדרת כאן כדי שהממשק יוכל להיבנות לפני שהמסד
 * נפתח, וכדי שסדר התצוגה יהיה שלנו ולא סדר השורות במסד.
 */

export const TREE_NUTS_ID = 'tree_nuts';

export interface Allergen {
  id: string;
  labelHe: string;
  parentId: string | null;
}

export const ALLERGEN_LIST: readonly Allergen[] = [
  { id: 'gluten', labelHe: 'גלוטן', parentId: null },
  { id: 'milk', labelHe: 'חלב', parentId: null },
  { id: 'eggs', labelHe: 'ביצים', parentId: null },
  { id: 'peanuts', labelHe: 'בוטנים', parentId: null },
  { id: 'sesame', labelHe: 'שומשום', parentId: null },
  { id: 'soy', labelHe: 'סויה', parentId: null },
  { id: TREE_NUTS_ID, labelHe: 'אגוזי עץ', parentId: null },
  { id: 'almond', labelHe: 'שקד', parentId: TREE_NUTS_ID },
  { id: 'walnut', labelHe: 'אגוז מלך', parentId: TREE_NUTS_ID },
  { id: 'cashew', labelHe: 'קשיו', parentId: TREE_NUTS_ID },
  { id: 'pecan', labelHe: 'פקאן', parentId: TREE_NUTS_ID },
  { id: 'pistachio', labelHe: 'פיסטוק', parentId: TREE_NUTS_ID },
  { id: 'hazelnut', labelHe: 'אגוז לוז', parentId: TREE_NUTS_ID },
  { id: 'macadamia', labelHe: 'מקדמיה', parentId: TREE_NUTS_ID },
  { id: 'brazil_nut', labelHe: 'אגוז ברזיל', parentId: TREE_NUTS_ID },
  { id: 'fish', labelHe: 'דגים', parentId: null },
  { id: 'crustaceans', labelHe: 'סרטנים', parentId: null },
  { id: 'molluscs', labelHe: 'רכיכות', parentId: null },
  { id: 'mustard', labelHe: 'חרדל', parentId: null },
  { id: 'celery', labelHe: 'סלרי', parentId: null },
  { id: 'lupin', labelHe: 'לופין', parentId: null },
  { id: 'sulphites', labelHe: 'סולפיטים', parentId: null },
];

const BY_ID = new Map(ALLERGEN_LIST.map((allergen) => [allergen.id, allergen]));

export function getAllergen(id: string): Allergen | undefined {
  return BY_ID.get(id);
}

export function labelOf(id: string): string {
  return BY_ID.get(id)?.labelHe ?? id;
}

export function topLevelAllergens(): Allergen[] {
  return ALLERGEN_LIST.filter((allergen) => allergen.parentId === null);
}

export function subtypesOf(parentId: string): Allergen[] {
  return ALLERGEN_LIST.filter((allergen) => allergen.parentId === parentId);
}

export function ancestorsOf(id: string): string[] {
  const chain: string[] = [];
  let current = BY_ID.get(id)?.parentId ?? null;
  while (current) {
    chain.push(current);
    current = BY_ID.get(current)?.parentId ?? null;
  }
  return chain;
}

/**
 * בחירת אגוז-אב תופסת את כל בניו.
 *
 * מי שמסנן אגוזי עץ חייב שיוסתר גם מוצר שמסומן קשיו בלבד.
 */
export function expandSelection(selected: Iterable<string>): Set<string> {
  const expanded = new Set(selected);
  for (const id of Array.from(expanded)) {
    for (const subtype of subtypesOf(id)) {
      expanded.add(subtype.id);
    }
  }
  return expanded;
}
