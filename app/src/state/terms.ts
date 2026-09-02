/**
 * מתי צריך להציג את שער התנאים.
 *
 * השער מוצג בכל כניסה, כלומר בפתיחה מאפס וגם בחזרה מהרקע אחרי יותר
 * מ-30 דקות. הסף קיים כדי שהוצאת הטלפון מהכיס בין מדף למדף לא תעלה
 * חמש שניות בכל פעם.
 *
 * חשוב לומר את המגבלה בגלוי: שער שחוזר מאמן אנשים ללחוץ בלי לקרוא.
 * המשקל המשפטי האמיתי נשען על הפס האדום הקבוע במסך המוצר, שמופיע
 * ברגע ההחלטה עצמו.
 */

import AsyncStorage from '@react-native-async-storage/async-storage';

import { TERMS_REGATE_AFTER_MINUTES, TERMS_VERSION } from '../legal/copy';

const ACCEPTED_VERSION_KEY = 'allergen.terms.acceptedVersion';
const ACCEPTED_AT_KEY = 'allergen.terms.acceptedAt';

export interface TermsState {
  acceptedVersion: number | null;
  acceptedAt: Date | null;
}

export async function readTermsState(): Promise<TermsState> {
  const [version, acceptedAt] = await Promise.all([
    AsyncStorage.getItem(ACCEPTED_VERSION_KEY),
    AsyncStorage.getItem(ACCEPTED_AT_KEY),
  ]);
  const parsedDate = acceptedAt ? new Date(acceptedAt) : null;
  return {
    acceptedVersion: version ? Number(version) : null,
    acceptedAt: parsedDate && !Number.isNaN(parsedDate.getTime()) ? parsedDate : null,
  };
}

export async function recordAcceptance(now: Date = new Date()): Promise<void> {
  await AsyncStorage.multiSet([
    [ACCEPTED_VERSION_KEY, String(TERMS_VERSION)],
    [ACCEPTED_AT_KEY, now.toISOString()],
  ]);
}

/**
 * גרסת תנאים חדשה מבטלת כל אישור קודם, וכך גם היעדר אישור או אישור
 * ישן מדי.
 */
export function needsAcceptance(state: TermsState, now: Date = new Date()): boolean {
  if (state.acceptedVersion !== TERMS_VERSION) return true;
  if (!state.acceptedAt) return true;
  const minutesSince = (now.getTime() - state.acceptedAt.getTime()) / 60000;
  return minutesSince >= TERMS_REGATE_AFTER_MINUTES;
}
