/**
 * נרמול טקסט עברי לחיפוש.
 *
 * מראה של pipeline/allergen_pipeline/text/hebrew.py. האינדקס נבנה בפייתון
 * והשאילתה רצה כאן, ולכן כל שינוי באחד מחייב שינוי זהה בשני ובניית תמונת
 * מצב מחדש. הבדיקות בשני הצדדים בודקות את אותם מקרים בכוונה.
 */

const NIQQUD = /[֑-ׇ]/g;
const QUOTES = /[׳״'"‘’“”ʼ`]/g;
const DASHES = /[-‐‑‒–—―_/\\|]+/g;
const NON_WORD = /[^\p{L}\p{N}]+/gu;
const WHITESPACE = /\s+/g;
const NON_DIGITS = /[^0-9]/g;
const DIGITS_ONLY = /^[0-9\s-]+$/;

const FINAL_LETTERS: Record<string, string> = {
  ך: 'כ',
  ם: 'מ',
  ן: 'נ',
  ף: 'פ',
  ץ: 'צ',
};

/**
 * תחיליות נפוצות, ארוכות קודם, כדי שהגזירה תנסה את המפורשת יותר תחילה.
 */
const PREFIXES = [
  'וכש',
  'ולכ',
  'כש',
  'לכ',
  'מה',
  'שה',
  'וה',
  'וב',
  'ול',
  'ומ',
  'וש',
  'ו',
  'ה',
  'ב',
  'ל',
  'מ',
  'ש',
  'כ',
];

/** אורך הגזע המינימלי שנשאר אחרי גזירת תחילית. */
export const MIN_STEM_LENGTH = 3;

export const MIN_BARCODE_DIGITS = 8;
export const MAX_BARCODE_DIGITS = 14;

export function stripNiqqud(text: string): string {
  return text.normalize('NFC').replace(NIQQUD, '');
}

/** מביא טקסט לצורה קנונית להשוואה ולחיפוש. */
export function normalize(text: string | null | undefined): string {
  if (!text) return '';
  let result = stripNiqqud(text);
  result = result.replace(QUOTES, '');
  result = result.replace(DASHES, ' ');
  result = result.replace(NON_WORD, ' ');
  result = result.replace(/[ךםןףץ]/g, (letter) => FINAL_LETTERS[letter]);
  result = result.replace(WHITESPACE, ' ').trim();
  return result.toLowerCase();
}

export function tokenize(text: string | null | undefined): string[] {
  const normalized = normalize(text);
  return normalized ? normalized.split(' ') : [];
}

/** גוזר תחילית אחת מהאסימון, אם נשאר גזע ארוך מספיק. */
export function stripPrefix(token: string): string | null {
  for (const prefix of PREFIXES) {
    if (!token.startsWith(prefix)) continue;
    const stem = token.slice(prefix.length);
    if (stem.length >= MIN_STEM_LENGTH) return stem;
  }
  return null;
}

/** האסימון עצמו, ואחריו הגזע בלי תחילית אם קיים. */
export function tokenVariants(token: string): string[] {
  const stem = stripPrefix(token);
  return stem && stem !== token ? [token, stem] : [token];
}

export function normalizeBarcode(text: string | null | undefined): string {
  return (text ?? '').replace(NON_DIGITS, '');
}

/**
 * האם השאילתה היא ברקוד ולא טקסט חופשי.
 *
 * מפריד בין שני מצבי החיפוש בשדה האחד: רק ספרות ומפרידים, ואורך בטווח
 * של ברקודי מסחר.
 */
export function looksLikeBarcode(text: string | null | undefined): boolean {
  if (!text) return false;
  const trimmed = text.trim();
  if (!DIGITS_ONLY.test(trimmed)) return false;
  const digits = normalizeBarcode(trimmed);
  return digits.length >= MIN_BARCODE_DIGITS && digits.length <= MAX_BARCODE_DIGITS;
}

/**
 * בונה ביטוי FTS5 מטקסט חופשי.
 *
 * כל אסימון הופך להתאמת תחילית, וכל האסימונים נדרשים יחד. גרשיים
 * בשאילתה נעלמים כבר בנרמול, ולכן אין דרך להזריק תחביר FTS.
 */
export function toFtsQuery(text: string): string {
  const tokens = tokenize(text);
  if (tokens.length === 0) return '';
  return tokens.map((token) => `"${token}"*`).join(' AND ');
}
