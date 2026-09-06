/** Validate a candidate before replacing the active catalog; retain a recoverable backup. */
import { Asset } from 'expo-asset';
import * as FileSystem from 'expo-file-system';
import * as SQLite from 'expo-sqlite';
import { SNAPSHOT_FILE, closeSnapshot, isSchemaSupported, readMeta, type SnapshotMeta } from './snapshot';

const DIRECTORY = `${FileSystem.documentDirectory}SQLite`;
const ACTIVE = `${DIRECTORY}/${SNAPSHOT_FILE}`;
const CANDIDATE_NAME = 'snapshot-candidate.sqlite';
const CANDIDATE = `${DIRECTORY}/${CANDIDATE_NAME}`;
const BACKUP_NAME = 'snapshot-backup.sqlite';
const BACKUP = `${DIRECTORY}/${BACKUP_NAME}`;
export type BootstrapOutcome =
  | { kind: 'ready'; productCount: number; builtAt: Date | null }
  | { kind: 'failed'; reason: string };

let pending: Promise<unknown> = Promise.resolve();
function exclusive(action: () => Promise<BootstrapOutcome>): Promise<BootstrapOutcome> {
  const result = pending.then(action, action);
  pending = result.catch(() => undefined);
  return result;
}
async function ensureDirectory(): Promise<void> {
  await FileSystem.makeDirectoryAsync(DIRECTORY, { intermediates: true });
}
function ready(meta: SnapshotMeta): BootstrapOutcome {
  return { kind: 'ready', productCount: meta.productCount, builtAt: meta.builtAt };
}
function failure(error: unknown): BootstrapOutcome {
  return { kind: 'failed', reason: error instanceof Error ? error.message : 'המאגר לא נטען' };
}

export async function validateSnapshot(name: string): Promise<SnapshotMeta> {
  const db = await SQLite.openDatabaseAsync(name, { useNewConnection: true });
  try {
    await db.execAsync('PRAGMA query_only = ON;');
    const integrity = await db.getFirstAsync<{ integrity_check: string }>('PRAGMA integrity_check');
    if (integrity?.integrity_check !== 'ok') throw new Error('קובץ המאגר אינו תקין');
    if (await db.getFirstAsync('PRAGMA foreign_key_check')) throw new Error('קשרים לא תקינים במאגר');
    const meta = await readMeta(db);
    if (!isSchemaSupported(meta)) throw new Error(`גרסת מאגר ${meta.schemaVersion} אינה נתמכת`);
    const count = await db.getFirstAsync<{ total: number; with_data: number }>(
      'SELECT COUNT(*) AS total, SUM(has_allergen_data) AS with_data FROM products',
    );
    if (!count || count.total < 1 || count.with_data < 1 ||
        count.total !== meta.productCount || count.with_data !== meta.withAllergenData) {
      throw new Error('נתוני המאגר חסרים או אינם תואמים');
    }
    await db.getFirstAsync('SELECT barcode FROM products_fts LIMIT 1');
    await db.getFirstAsync('SELECT allergen_id, level, sources, observed_on FROM product_allergens LIMIT 1');
    await db.getFirstAsync('SELECT message FROM product_conflicts LIMIT 1');
    return meta;
  } finally {
    await db.closeAsync();
  }
}

async function promote(): Promise<BootstrapOutcome> {
  const meta = await validateSnapshot(CANDIDATE_NAME);
  const existed = (await FileSystem.getInfoAsync(ACTIVE)).exists;
  if (existed) {
    // Reject large unexplained regressions before touching the active catalog.
    try {
      const old = await validateSnapshot(SNAPSHOT_FILE);
      if (meta.productCount < old.productCount * 0.8 ||
          meta.withAllergenData < old.withAllergenData * 0.8) {
        throw new Error('ירידה חריגה בכיסוי המאגר');
      }
    } catch (error) {
      // Invalid/obsolete active catalogs can be replaced by a validated candidate.
      if (error instanceof Error && error.message === 'ירידה חריגה בכיסוי המאגר') throw error;
    }
  }
  await closeSnapshot();
  if (existed) await FileSystem.copyAsync({ from: ACTIVE, to: BACKUP });
  try {
    await FileSystem.deleteAsync(ACTIVE, { idempotent: true });
    await FileSystem.moveAsync({ from: CANDIDATE, to: ACTIVE });
    return ready(await validateSnapshot(SNAPSHOT_FILE));
  } catch (error) {
    if (existed) await FileSystem.copyAsync({ from: BACKUP, to: ACTIVE });
    throw error;
  }
}

export function installBundledSnapshot(force = false): Promise<BootstrapOutcome> {
  return exclusive(async () => {
    try {
      await ensureDirectory();
      if (!force) {
        if ((await FileSystem.getInfoAsync(ACTIVE)).exists) {
          try { return ready(await validateSnapshot(SNAPSHOT_FILE)); } catch { /* rebuild below */ }
        }
        if ((await FileSystem.getInfoAsync(BACKUP)).exists) {
          try {
            const meta = await validateSnapshot(BACKUP_NAME);
            await closeSnapshot();
            await FileSystem.copyAsync({ from: BACKUP, to: ACTIVE });
            return ready(meta);
          } catch { /* fall back to the bundled catalog */ }
        }
      }
      const asset = Asset.fromModule(require('../../assets/allergen-snapshot.sqlite'));
      await asset.downloadAsync();
      if (!asset.localUri) throw new Error('תמונת המצב הארוזה לא נמצאה');
      await FileSystem.copyAsync({ from: asset.localUri, to: CANDIDATE });
      return await promote();
    } catch (error) { return failure(error); }
    finally { await FileSystem.deleteAsync(CANDIDATE, { idempotent: true }).catch(() => undefined); }
  });
}

export function replaceSnapshotFrom(url: string): Promise<BootstrapOutcome> {
  return exclusive(async () => {
    try {
      if (!url.startsWith('https://')) throw new Error('עדכון מאגר דורש כתובת HTTPS');
      await ensureDirectory();
      const download = await FileSystem.downloadAsync(url, CANDIDATE);
      if (download.status !== 200) throw new Error(`ההורדה נכשלה (${download.status})`);
      return await promote();
    } catch (error) { return failure(error); }
    finally { await FileSystem.deleteAsync(CANDIDATE, { idempotent: true }).catch(() => undefined); }
  });
}
