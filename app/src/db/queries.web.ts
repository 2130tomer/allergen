/**
 * שכבת נתונים לבנייה ל-web.
 *
 * ב-web אין SQLite ואין מצלמה, ולכן הבנייה הזו אינה האפליקציה אלא כלי
 * לבדיקת הממשק: אותם מסכים, אותם רכיבים, ואותם נתונים אמיתיים שנחתכו
 * מתמונת מצב שנבנתה מהצינור.
 *
 * Metro בוחר את הקובץ הזה על פני queries.ts רק בבנייה ל-web, ולכן
 * המסלול הנייטיבי אינו מושפע כלל.
 */

import type { AllergenLevels, Level } from '../domain/filter';
import { looksLikeBarcode, normalize, normalizeBarcode } from '../text/hebrew';
import type {
  CatalogStats,
  Department,
  ProductDetail,
  ProductSummary,
  SearchResults,
} from './queries';
import preview from './fixtures/preview.json';

export { HIDDEN_FROM_BROWSE } from './queries';

interface AllergenRecord {
  levels: Record<string, Level>;
  sources: string[];
  inferred: string[];
}

const PRODUCTS = preview.products as unknown as ProductSummary[];
const ALLERGENS = Object.fromEntries(Object.entries(preview.allergens).map(([barcode, raw]) => {
  const entry = raw as unknown as AllergenRecord;
  const levels = Object.fromEntries(Object.entries(entry.levels).filter(([, level]) =>
    level !== 'absent' || !entry.sources.includes('declared_free_from')));
  return [barcode, { ...entry, levels }];
})) as Record<string, AllergenRecord>;
const DEPARTMENTS = preview.departments as unknown as Department[];
const CONFLICTS = (preview as { conflicts?: Record<string, { message: string }[]> })
  .conflicts ?? {};

const HIDDEN = ['non_food'];

export async function listDepartments(includeHidden = false): Promise<Department[]> {
  return DEPARTMENTS.filter(
    (department) => includeHidden || !HIDDEN.includes(department.id),
  );
}

export async function countProductsInDepartment(departmentId: string): Promise<number> {
  return (await listByDepartment(departmentId)).length;
}

export async function catalogStats(): Promise<CatalogStats> {
  const food = PRODUCTS.filter((product) => product.departmentId !== 'non_food');
  return {
    foodProducts: food.length,
    withAllergenData: food.filter((product) => product.hasAllergenData).length,
    withImage: food.filter((product) => product.imageUrl).length,
  };
}

export async function listByDepartment(
  departmentId: string,
  limit = 200,
  offset = 0,
): Promise<ProductSummary[]> {
  const children = DEPARTMENTS.filter((d) => d.parentId === departmentId).map(
    (d) => d.id,
  );
  const wanted = new Set([departmentId, ...children]);
  return PRODUCTS.filter((product) => wanted.has(product.departmentId)).slice(
    offset,
    offset + limit,
  );
}

export async function findByBarcode(raw: string): Promise<ProductSummary | null> {
  const digits = normalizeBarcode(raw);
  return PRODUCTS.find((product) => product.barcode === digits) ?? null;
}

export async function search(query: string, limit = 100): Promise<SearchResults> {
  if (looksLikeBarcode(query)) {
    const product = await findByBarcode(query);
    return { kind: 'barcode', products: product ? [product] : [], departments: [] };
  }

  const needle = normalize(query);
  if (!needle) return { kind: 'text', products: [], departments: [] };

  const products = PRODUCTS.filter((product) =>
    normalize(`${product.name} ${product.manufacturer ?? ''}`).includes(needle),
  ).slice(0, limit);

  const departments = DEPARTMENTS.filter((department) =>
    normalize(department.labelHe).includes(needle),
  );

  return { kind: 'text', products, departments };
}

export async function levelsFor(
  barcodes: string[],
): Promise<Record<string, AllergenLevels>> {
  const result: Record<string, AllergenLevels> = {};
  for (const barcode of barcodes) {
    result[barcode] = ALLERGENS[barcode]?.levels ?? {};
  }
  return result;
}

export async function loadProduct(barcode: string): Promise<ProductDetail | null> {
  const summary = await findByBarcode(barcode);
  if (!summary) return null;
  const record = ALLERGENS[summary.barcode];
  return {
    ...summary,
    levels: record?.levels ?? {},
    sources: record?.sources ?? [],
    conflicts: (CONFLICTS[summary.barcode] ?? []).map((row) => row.message),
    inferredAllergenIds: record?.inferred ?? [],
  };
}
