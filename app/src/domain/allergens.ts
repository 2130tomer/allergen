/**
 * הרשימה הסגורה של האלרגנים וההיררכיה שביניהם.
 *
 * מראה של pipeline/allergen_pipeline/domain/allergens.py, ונוצר ממנו
 * אוטומטית. אין לערוך ידנית: כל שינוי מתחיל בצד הפייתון.
 *
 * הרשימה נטענת גם מתמונת המצב, אך מוגדרת כאן כדי שהממשק יוכל להיבנות
 * לפני שהמסד נפתח, וכדי שסדר התצוגה יהיה שלנו ולא סדר השורות במסד.
 */

export const TREE_NUTS_ID = 'tree_nuts';

export interface Allergen {
  id: string;
  labelHe: string;
  parentId: string | null;
  /** הערה קצרה שמוצגת כשהשם לבדו אינו חד-משמעי. */
  noteHe?: string;
}

export const ALLERGEN_LIST: readonly Allergen[] = [
  { id: "gluten", labelHe: "גלוטן", parentId: null },
  { id: "wheat", labelHe: "חיטה", parentId: "gluten" },
  { id: "barley", labelHe: "שעורה", parentId: "gluten" },
  { id: "rye", labelHe: "שיפון", parentId: "gluten" },
  { id: "oats", labelHe: "שיבולת שועל", parentId: null },
  { id: "spelt", labelHe: "כוסמין", parentId: "gluten" },
  { id: "milk", labelHe: "חלב", parentId: null },
  { id: "lactose", labelHe: "לקטוז", parentId: null, noteHe: "רגישות לסוכר החלב. אינו זהה לאלרגיה לחלבון חלב." },
  { id: "eggs", labelHe: "ביצים", parentId: null },
  { id: "peanuts", labelHe: "בוטנים", parentId: null },
  { id: "soy", labelHe: "סויה", parentId: null },
  { id: "sesame", labelHe: "שומשום", parentId: null },
  { id: "fish", labelHe: "דגים", parentId: null },
  { id: "crustaceans", labelHe: "סרטנים", parentId: null },
  { id: "molluscs", labelHe: "רכיכות", parentId: null },
  { id: "tree_nuts", labelHe: "אגוזי עץ", parentId: null },
  { id: "almond", labelHe: "שקד", parentId: "tree_nuts" },
  { id: "walnut", labelHe: "אגוז מלך", parentId: "tree_nuts" },
  { id: "cashew", labelHe: "קשיו", parentId: "tree_nuts" },
  { id: "pecan", labelHe: "פקאן", parentId: "tree_nuts" },
  { id: "pistachio", labelHe: "פיסטוק", parentId: "tree_nuts" },
  { id: "hazelnut", labelHe: "אגוז לוז", parentId: "tree_nuts" },
  { id: "macadamia", labelHe: "מקדמיה", parentId: "tree_nuts" },
  { id: "brazil_nut", labelHe: "אגוז ברזיל", parentId: "tree_nuts" },
  { id: "pine_nut", labelHe: "צנוברים", parentId: "tree_nuts" },
  { id: "chestnut", labelHe: "ערמונים", parentId: "tree_nuts" },
  { id: "legumes", labelHe: "קטניות", parentId: null },
  { id: "fava_bean", labelHe: "פול", parentId: "legumes", noteHe: "רלוונטי לנשאי חסר G6PD (פאביזם)." },
  { id: "chickpea", labelHe: "חומוס", parentId: "legumes" },
  { id: "lentil", labelHe: "עדשים", parentId: "legumes" },
  { id: "pea", labelHe: "אפונה", parentId: "legumes" },
  { id: "bean", labelHe: "שעועית", parentId: "legumes" },
  { id: "mustard", labelHe: "חרדל", parentId: null },
  { id: "celery", labelHe: "סלרי", parentId: null },
  { id: "lupin", labelHe: "לופין", parentId: null },
  { id: "sulphites", labelHe: "סולפיטים", parentId: null },
  { id: "corn", labelHe: "תירס", parentId: null },
  { id: "coconut", labelHe: "קוקוס", parentId: null },
  { id: "sunflower", labelHe: "חמניות", parentId: null },
  { id: "buckwheat", labelHe: "כוסמת", parentId: null },
  { id: "gelatin", labelHe: "ג'לטין", parentId: null },
  { id: "yeast", labelHe: "שמרים", parentId: null },
];

/**
 * גרירות בטיחות שאינן חלק מההיררכיה.
 *
 * בחירת "קטניות" גוררת בוטנים, סויה ולופין, שמוצגים בנפרד כדי שלא
 * ייקברו מתחת לקטגוריה. ראו את ההסבר המלא בצד הפייתון.
 */
const IMPLIES: Record<string, readonly string[]> = {
  "legumes": ["peanuts", "soy", "lupin"],
};

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
 * הרחבת בחירה לכל מה שהיא תופסת בפועל.
 *
 * שני מנגנונים: ירידה בהיררכיה (אגוזי עץ תופס קשיו) וגרירת בטיחות
 * (קטניות תופס בוטנים). שניהם מורחבים עד למיצוי.
 */
export function expandSelection(selected: Iterable<string>): Set<string> {
  const expanded = new Set(selected);
  const pending = Array.from(expanded);
  while (pending.length > 0) {
    const current = pending.pop() as string;
    const reached = [
      ...subtypesOf(current).map((allergen) => allergen.id),
      ...(IMPLIES[current] ?? []),
    ];
    for (const id of reached) {
      if (!expanded.has(id)) {
        expanded.add(id);
        pending.push(id);
      }
    }
  }
  return expanded;
}
