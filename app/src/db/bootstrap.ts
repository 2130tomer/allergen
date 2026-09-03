/**
 * התקנת תמונת המצב על המכשיר. ראו ADR-0003.
 *
 * האפליקציה נשלחת עם תמונת מצב ארוזה, כדי שהיא תעבוד מהשנייה הראשונה
 * ובלי רשת. בהפעלה הראשונה הקובץ מועתק לספריית ה-SQLite, ומשם והלאה
 * הוא נפתח משם.
 *
 * הרענון הוא החלפה של אותו קובץ. אין מיזוג בצד הלקוח: תמונת מצב היא
 * תוצר של הצינור בשלמותה, וחצי תמונה היא בדיוק המצב שבו מוצר נראה
 * כאילו אין לו אלרגנים.
 */

import { Asset } from 'expo-asset';
import * as FileSystem from 'expo-file-system';

import { SNAPSHOT_FILE, closeSnapshot, isSchemaSupported, readMeta } from './snapshot';

const SQLITE_DIRECTORY = `${FileSystem.documentDirectory}SQLite`;
const SNAPSHOT_PATH = `${SQLITE_DIRECTORY}/${SNAPSHOT_FILE}`;

export type BootstrapOutcome =
  | { kind: 'ready'; productCount: number; builtAt: Date | null }
  | { kind: 'failed'; reason: string };

async function ensureDirectory(): Promise<void> {
  const info = await FileSystem.getInfoAsync(SQLITE_DIRECTORY);
  if (!info.exists) {
    await FileSystem.makeDirectoryAsync(SQLITE_DIRECTORY, { intermediates: true });
  }
}

/**
 * מתקין את תמונת המצב הארוזה אם אין עדיין קובץ על המכשיר.
 *
 * `force` מחליף גם קובץ קיים, לשימוש אחרי הורדת תמונה חדשה.
 */
export async function installBundledSnapshot(force = false): Promise<BootstrapOutcome> {
  try {
    await ensureDirectory();
    const existing = await FileSystem.getInfoAsync(SNAPSHOT_PATH);

    if (!existing.exists || force) {
      await closeSnapshot();
      // require סטטי בכוונה: המאגד צריך לראות את הנכס בזמן בנייה.
      const asset = Asset.fromModule(require('../../assets/allergen-snapshot.sqlite'));
      await asset.downloadAsync();
      if (!asset.localUri) {
        return { kind: 'failed', reason: 'תמונת המצב הארוזה לא נמצאה' };
      }
      await FileSystem.copyAsync({ from: asset.localUri, to: SNAPSHOT_PATH });
    }

    const meta = await readMeta();
    if (!isSchemaSupported(meta)) {
      return {
        kind: 'failed',
        reason: `גרסת סכימה ${meta.schemaVersion} אינה נתמכת בגרסת האפליקציה הזו`,
      };
    }

    return { kind: 'ready', productCount: meta.productCount, builtAt: meta.builtAt };
  } catch (error) {
    return {
      kind: 'failed',
      reason: error instanceof Error ? error.message : 'התקנת תמונת המצב נכשלה',
    };
  }
}

/**
 * מוריד תמונת מצב חדשה ומחליף את הקיימת.
 *
 * ההחלפה מתבצעת רק אחרי שההורדה הושלמה במלואה, כדי שכשל באמצע לא
 * ישאיר את המכשיר עם קובץ חתוך.
 */
export async function replaceSnapshotFrom(url: string): Promise<BootstrapOutcome> {
  const staging = `${FileSystem.cacheDirectory}snapshot-download.sqlite`;
  try {
    const download = await FileSystem.downloadAsync(url, staging);
    if (download.status !== 200) {
      return { kind: 'failed', reason: `ההורדה נכשלה (${download.status})` };
    }

    await ensureDirectory();
    await closeSnapshot();
    await FileSystem.moveAsync({ from: staging, to: SNAPSHOT_PATH });

    const meta = await readMeta();
    if (!isSchemaSupported(meta)) {
      return {
        kind: 'failed',
        reason: `גרסת סכימה ${meta.schemaVersion} אינה נתמכת`,
      };
    }
    return { kind: 'ready', productCount: meta.productCount, builtAt: meta.builtAt };
  } catch (error) {
    await FileSystem.deleteAsync(staging, { idempotent: true });
    return {
      kind: 'failed',
      reason: error instanceof Error ? error.message : 'רענון תמונת המצב נכשל',
    };
  }
}
