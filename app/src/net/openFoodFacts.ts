/**
 * גיבוי חי ל-Open Food Facts, לברקוד שאינו במאגר המקומי.
 *
 * זהו המסלול היחיד שבו האפליקציה פונה לרשת כדי לענות על שאלת אלרגנים,
 * והוא תמיד שני בתור. אם אין רשת, אין תשובה, ולא ניחוש.
 *
 * מיפוי התגיות זהה לזה שבצד השרת, כולל השמירה על ההפרדה בין השדות:
 * allergens_tags הוא מכיל, traces_tags הוא עלול להכיל. זו בדיוק ההבחנה
 * שאתרי היצרנים מוחקים, ולכן היא נשמרת גם כאן. ראו ADR-0004.
 */

import type { ProductDetail } from '../db/queries';
import type { Level } from '../domain/filter';

const PRODUCT_URL = 'https://world.openfoodfacts.org/api/v2/product';
const FIELDS = [
  'code',
  'product_name',
  'product_name_he',
  'brands',
  'allergens_tags',
  'traces_tags',
  'image_front_url',
].join(',');

const REQUEST_TIMEOUT_MS = 6000;

const TAG_TO_ALLERGEN: Record<string, string> = {
  gluten: 'gluten',
  wheat: 'gluten',
  גלוטן: 'gluten',
  חיטה: 'gluten',
  milk: 'milk',
  חלב: 'milk',
  eggs: 'eggs',
  egg: 'eggs',
  ביצים: 'eggs',
  peanuts: 'peanuts',
  peanut: 'peanuts',
  בוטנים: 'peanuts',
  soybeans: 'soy',
  soy: 'soy',
  סויה: 'soy',
  'sesame-seeds': 'sesame',
  sesame: 'sesame',
  שומשום: 'sesame',
  fish: 'fish',
  דגים: 'fish',
  crustaceans: 'crustaceans',
  סרטנים: 'crustaceans',
  molluscs: 'molluscs',
  רכיכות: 'molluscs',
  nuts: 'tree_nuts',
  'tree-nuts': 'tree_nuts',
  אגוזים: 'tree_nuts',
  almonds: 'almond',
  שקדים: 'almond',
  walnuts: 'walnut',
  cashew: 'cashew',
  'cashew-nuts': 'cashew',
  'pecan-nuts': 'pecan',
  pistachio: 'pistachio',
  pistachios: 'pistachio',
  hazelnuts: 'hazelnut',
  'macadamia-nuts': 'macadamia',
  'brazil-nuts': 'brazil_nut',
  mustard: 'mustard',
  חרדל: 'mustard',
  celery: 'celery',
  סלרי: 'celery',
  lupin: 'lupin',
  לופין: 'lupin',
  'sulphur-dioxide-and-sulphites': 'sulphites',
  sulphites: 'sulphites',
  סולפיטים: 'sulphites',
};

function mapTags(tags: unknown): string[] {
  if (!Array.isArray(tags)) return [];
  const mapped = new Set<string>();
  for (const tag of tags) {
    if (typeof tag !== 'string') continue;
    const key = (tag.includes(':') ? tag.split(':').pop() ?? '' : tag).trim().toLowerCase();
    const allergenId = TAG_TO_ALLERGEN[key];
    if (allergenId) mapped.add(allergenId);
  }
  return [...mapped];
}

export async function fetchFromOpenFoodFacts(
  barcode: string,
): Promise<ProductDetail | null> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);

  try {
    const response = await fetch(
      `${PRODUCT_URL}/${encodeURIComponent(barcode)}.json?fields=${FIELDS}`,
      { signal: controller.signal, headers: { 'User-Agent': 'Allergen-IL/0.1' } },
    );
    if (!response.ok) return null;

    const payload = (await response.json()) as {
      status?: number;
      product?: Record<string, unknown>;
    };
    if (payload.status !== 1 || !payload.product) return null;

    const product = payload.product;
    const contains = mapTags(product.allergens_tags);
    const traces = mapTags(product.traces_tags);

    const levels: Record<string, Level> = {};
    for (const id of contains) levels[id] = 'contains';
    for (const id of traces) {
      // מכיל גובר על עלול להכיל כשהאלרגן מופיע בשני השדות.
      if (!levels[id]) levels[id] = 'may_contain';
    }

    const name =
      (product.product_name_he as string) || (product.product_name as string) || barcode;

    return {
      barcode,
      name,
      manufacturer: (product.brands as string) ?? null,
      departmentId: 'unclassified',
      quantity: null,
      unit: null,
      imageUrl: (product.image_front_url as string) ?? null,
      imageSource: 'Open Food Facts',
      isActive: true,
      needsReview: false,
      // מוצר שהתקבל מ-Open Food Facts בזמן אמת אינו נושא את רשימת
      // הרכיבים שלנו, ולכן אינו זכאי לניסוח "רשימת רכיבים ידועה".
      ingredientsKnown: false,
      hasAllergenData: contains.length + traces.length > 0,
      allergensObservedOn: new Date().toISOString().slice(0, 10),
      levels,
      sources: ['open_food_facts'],
      conflicts: [],
      inferredAllergenIds: [],
    };
  } catch {
    // אין רשת, פסק זמן, או תשובה לא צפויה. אין תשובה, ולא ניחוש.
    return null;
  } finally {
    clearTimeout(timeout);
  }
}
