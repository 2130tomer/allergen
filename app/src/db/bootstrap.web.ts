/**
 * ב-web אין קובץ SQLite להתקין, ולכן ההתקנה מסתיימת מיד.
 *
 * הבנייה ל-web היא כלי לבדיקת ממשק בלבד ואינה האפליקציה. הנתונים
 * מגיעים ממקבע, ולא ממאגר שהצינור בנה.
 */

import type { BootstrapOutcome } from './bootstrap';

export type { BootstrapOutcome } from './bootstrap';

export async function installBundledSnapshot(): Promise<BootstrapOutcome> {
  return { kind: 'ready', productCount: 0, builtAt: null };
}

export async function replaceSnapshotFrom(): Promise<BootstrapOutcome> {
  return { kind: 'failed', reason: 'רענון מאגר אינו נתמך בדפדפן' };
}
