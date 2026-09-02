/**
 * שאילתות מול תמונת המצב המקומית.
 *
 * שדה החיפוש אחד, ולכן השאילתה מחליטה בעצמה אם היא ברקוד או טקסט.
 * טקסט עובר את אותו נרמול שבו נבנה האינדקס בפייתון; בלעדיו אות סופית
 * אחת מפילה את החיפוש.
 */

import { normalizeBarcode, looksLikeBarcode, toFtsQuery } from '../text/hebrew';
import type { AllergenLevels, Level } from '../domain/filter';
import { openSnapshot } from './snapshot';

export interface ProductSummary {
  barcode: string;
  name: string;
  manufacturer: string | null;
  departmentId: string;
  quantity: string | null;
  unit: string | null;
  imageUrl: string | null;
  imageSource: string | null;
  isActive: boolean;
  needsReview: boolean;
  hasAllergenData: boolean;
  allergensObservedOn: string | null;
}

export interface ProductDetail extends ProductSummary {
  levels: AllergenLevels;
  sources: string[];
  conflicts: string[];
  inferredAllergenIds: string[];
}

export interface Department {
  id: string;
  labelHe: string;
  parentId: string | null;
}

interface ProductRow {
  barcode: string;
  name: string;
  manufacturer: string | null;
  department_id: string;
  quantity: string | null;
  unit: string | null;
  image_url: string | null;
  image_source: string | null;
  is_active: number;
  needs_review: number;
  has_allergen_data: number;
  allergens_observed_on: string | null;
}

const PRODUCT_COLUMNS = `
  barcode, name, manufacturer, department_id, quantity, unit,
  image_url, image_source, is_active, needs_review,
  has_allergen_data, allergens_observed_on
`;

function toSummary(row: ProductRow): ProductSummary {
  return {
    barcode: row.barcode,
    name: row.name,
    manufacturer: row.manufacturer,
    departmentId: row.department_id,
    quantity: row.quantity,
    unit: row.unit,
    imageUrl: row.image_url,
    imageSource: row.image_source,
    isActive: row.is_active === 1,
    needsReview: row.needs_review === 1,
    hasAllergenData: row.has_allergen_data === 1,
    allergensObservedOn: row.allergens_observed_on,
  };
}

export async function listDepartments(): Promise<Department[]> {
  const connection = await openSnapshot();
  const rows = await connection.getAllAsync<{
    id: string;
    label_he: string;
    parent_id: string | null;
  }>('SELECT id, label_he, parent_id FROM departments');
  return rows.map((row) => ({
    id: row.id,
    labelHe: row.label_he,
    parentId: row.parent_id,
  }));
}

export async function countProductsInDepartment(departmentId: string): Promise<number> {
  const connection = await openSnapshot();
  const row = await connection.getFirstAsync<{ total: number }>(
    `SELECT COUNT(*) AS total FROM products
       WHERE is_active = 1
         AND department_id IN (
           SELECT id FROM departments WHERE id = ? OR parent_id = ?
         )`,
    [departmentId, departmentId],
  );
  return row?.total ?? 0;
}

export async function listByDepartment(
  departmentId: string,
  limit = 200,
  offset = 0,
): Promise<ProductSummary[]> {
  const connection = await openSnapshot();
  const rows = await connection.getAllAsync<ProductRow>(
    `SELECT ${PRODUCT_COLUMNS} FROM products
       WHERE is_active = 1
         AND department_id IN (
           SELECT id FROM departments WHERE id = ? OR parent_id = ?
         )
       ORDER BY name
       LIMIT ? OFFSET ?`,
    [departmentId, departmentId, limit, offset],
  );
  return rows.map(toSummary);
}

export async function findByBarcode(raw: string): Promise<ProductSummary | null> {
  const connection = await openSnapshot();
  const digits = normalizeBarcode(raw);
  if (!digits) return null;
  const row = await connection.getFirstAsync<ProductRow>(
    `SELECT ${PRODUCT_COLUMNS} FROM products WHERE barcode = ?`,
    [digits],
  );
  return row ? toSummary(row) : null;
}

export interface SearchResults {
  kind: 'barcode' | 'text';
  products: ProductSummary[];
  departments: Department[];
}

/**
 * חיפוש חופשי אחד לשלושת המקרים: ברקוד, שם מוצר, ושם מחלקה.
 *
 * קלט של ספרות בלבד באורך ברקוד נחשב לברקוד; כל השאר טקסט.
 */
export async function search(query: string, limit = 100): Promise<SearchResults> {
  const connection = await openSnapshot();

  if (looksLikeBarcode(query)) {
    const product = await findByBarcode(query);
    return {
      kind: 'barcode',
      products: product ? [product] : [],
      departments: [],
    };
  }

  const ftsQuery = toFtsQuery(query);
  if (!ftsQuery) {
    return { kind: 'text', products: [], departments: [] };
  }

  const rows = await connection.getAllAsync<ProductRow>(
    `SELECT ${PRODUCT_COLUMNS} FROM products
       WHERE barcode IN (
         SELECT barcode FROM products_fts WHERE products_fts MATCH ?
       )
       AND is_active = 1
       ORDER BY name
       LIMIT ?`,
    [ftsQuery, limit],
  );

  const departmentRows = await connection.getAllAsync<{
    id: string;
    label_he: string;
    parent_id: string | null;
  }>('SELECT id, label_he, parent_id FROM departments WHERE label_he LIKE ?', [
    `%${query.trim()}%`,
  ]);

  return {
    kind: 'text',
    products: rows.map(toSummary),
    departments: departmentRows.map((row) => ({
      id: row.id,
      labelHe: row.label_he,
      parentId: row.parent_id,
    })),
  };
}

/**
 * רמות האלרגנים של קבוצת מוצרים, בשאילתה אחת.
 *
 * מוצר שאין לו שורות מקבל אובייקט ריק, וכל אלרגן בו נקרא כאין מידע.
 * זה המקום שבו היעדר נתון נשאר היעדר נתון ואינו הופך ללא מכיל.
 */
export async function levelsFor(
  barcodes: string[],
): Promise<Record<string, AllergenLevels>> {
  if (barcodes.length === 0) return {};
  const connection = await openSnapshot();
  const placeholders = barcodes.map(() => '?').join(', ');
  const rows = await connection.getAllAsync<{
    barcode: string;
    allergen_id: string;
    level: Level;
  }>(
    `SELECT barcode, allergen_id, level FROM product_allergens
       WHERE barcode IN (${placeholders})`,
    barcodes,
  );

  const byBarcode: Record<string, Record<string, Level>> = {};
  for (const barcode of barcodes) byBarcode[barcode] = {};
  for (const row of rows) {
    byBarcode[row.barcode][row.allergen_id] = row.level;
  }
  return byBarcode;
}

export async function loadProduct(barcode: string): Promise<ProductDetail | null> {
  const connection = await openSnapshot();
  const summary = await findByBarcode(barcode);
  if (!summary) return null;

  const allergenRows = await connection.getAllAsync<{
    allergen_id: string;
    level: Level;
    sources: string;
    level_inferred: number;
  }>(
    `SELECT allergen_id, level, sources, level_inferred
       FROM product_allergens WHERE barcode = ?`,
    [summary.barcode],
  );

  const conflictRows = await connection.getAllAsync<{ message: string }>(
    'SELECT message FROM product_conflicts WHERE barcode = ?',
    [summary.barcode],
  );

  const levels: Record<string, Level> = {};
  const sources = new Set<string>();
  const inferred: string[] = [];
  for (const row of allergenRows) {
    levels[row.allergen_id] = row.level;
    for (const source of row.sources.split(',').filter(Boolean)) {
      sources.add(source);
    }
    if (row.level_inferred === 1) inferred.push(row.allergen_id);
  }

  return {
    ...summary,
    levels,
    sources: [...sources],
    conflicts: conflictRows.map((row) => row.message),
    inferredAllergenIds: inferred,
  };
}
