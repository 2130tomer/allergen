/**
 * פתיחת תמונת המצב המקומית. ראו ADR-0003.
 *
 * כל החיפוש והסריקה רצים מהקובץ הזה. פנייה לרשת קיימת רק כגיבוי
 * לברקוד שאינו במאגר המקומי, ולתמונות. אין מצב שבו האפליקציה לא עונה
 * מול המדף בגלל קליטה.
 */

import * as FileSystem from 'expo-file-system';
import * as SQLite from 'expo-sqlite';

export const SNAPSHOT_FILE = 'allergen-snapshot.sqlite';
export const SUPPORTED_SCHEMA_VERSION = 2;

/** מעל הגיל הזה מוצגת למשתמש הודעה שהנתונים אינם מעודכנים. */
export const STALE_AFTER_DAYS = 14;

export interface SnapshotMeta {
  schemaVersion: number;
  builtAt: Date | null;
  productCount: number;
  withAllergenData: number;
}

let database: SQLite.SQLiteDatabase | null = null;

export async function isSnapshotInstalled(): Promise<boolean> {
  const path = `${FileSystem.documentDirectory}SQLite/${SNAPSHOT_FILE}`;
  const info = await FileSystem.getInfoAsync(path);
  return info.exists;
}

export async function openSnapshot(): Promise<SQLite.SQLiteDatabase> {
  if (database) return database;
  database = await SQLite.openDatabaseAsync(SNAPSHOT_FILE);
  await database.execAsync('PRAGMA query_only = ON;');
  return database;
}

export async function closeSnapshot(): Promise<void> {
  await database?.closeAsync();
  database = null;
}

export async function readMeta(connection?: SQLite.SQLiteDatabase): Promise<SnapshotMeta> {
  connection = connection ?? await openSnapshot();
  const rows = await connection.getAllAsync<{ key: string; value: string }>(
    'SELECT key, value FROM meta',
  );
  const values = Object.fromEntries(rows.map((row) => [row.key, row.value]));
  const builtAt = values.built_at ? new Date(values.built_at) : null;

  return {
    schemaVersion: Number(values.schema_version ?? 0),
    builtAt: builtAt && !Number.isNaN(builtAt.getTime()) ? builtAt : null,
    productCount: Number(values.product_count ?? 0),
    withAllergenData: Number(values.with_allergen_data ?? 0),
  };
}

export function isStale(meta: SnapshotMeta, now: Date = new Date()): boolean {
  if (!meta.builtAt) return true;
  const ageMs = now.getTime() - meta.builtAt.getTime();
  return ageMs > STALE_AFTER_DAYS * 24 * 60 * 60 * 1000;
}

/**
 * גרסת סכימה שאיננו יודעים לקרוא היא סיבה לרענן, לא לנחש.
 *
 * קריאה שגויה של תמונת מצב תיראה כמו מוצר בלי אלרגנים, וזו בדיוק
 * הטעות המסוכנת.
 */
export function isSchemaSupported(meta: SnapshotMeta): boolean {
  return meta.schemaVersion === SUPPORTED_SCHEMA_VERSION;
}
