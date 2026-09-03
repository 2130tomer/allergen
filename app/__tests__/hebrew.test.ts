/**
 * בדיקות הנרמול בצד הלקוח.
 *
 * המקרים כאן מכוונים בכוונה לאותם מקרים שנבדקים ב-pipeline/tests/
 * test_text_and_barcode.py. אם צד אחד משתנה והשני לא, החיפוש נשבר
 * בשקט: האינדקס יכיל צורה אחת והשאילתה תחפש אחרת.
 */

import {
  looksLikeBarcode,
  normalize,
  normalizeBarcode,
  stripPrefix,
  toFtsQuery,
  tokenVariants,
  tokenize,
} from '../src/text/hebrew';

const BAMBA = '7290000066318';

describe('נרמול', () => {
  it('משמיט מרכאות', () => {
    expect(normalize('"במבה"')).toBe(normalize('במבה'));
  });

  it('משמיט גרשיים עבריים', () => {
    expect(normalize('ק״ג')).toBe(normalize('קג'));
  });

  it('הופך מקף לרווח', () => {
    expect(normalize('קוקה-קולה')).toBe(normalize('קוקה קולה'));
  });

  it('משמיט ניקוד', () => {
    expect(normalize('בַּמְבָּה')).toBe(normalize('במבה'));
  });

  it('מאחד אותיות סופיות', () => {
    expect(normalize('לחם')).toBe(normalize('לחמ'));
  });

  it('מפריד ספרות שדבוקות לאותיות', () => {
    // נפוץ מאוד בקבצי הרשתות: 100ג, 32יח, 5סכיני.
    expect(tokenize('במבה 100ג')).toEqual(['במבה', '100', 'ג']);
    expect(tokenize('5סכיני גילוח')).toEqual(['5', 'סכיני', 'גילוח']);
  });

  it('מכווץ רווחים', () => {
    expect(normalize('  במבה   אסם  ')).toBe('במבה אסמ');
  });

  it('מוריד רישיות בלטינית', () => {
    expect(normalize('Coca Cola')).toBe('coca cola');
  });

  it('מחזיר מחרוזת ריקה על קלט ריק', () => {
    expect(normalize('')).toBe('');
    expect(normalize(null)).toBe('');
    expect(tokenize(undefined)).toEqual([]);
  });
});

describe('תחיליות', () => {
  it('גוזר תחילית כשנשאר גזע אמיתי', () => {
    expect(stripPrefix(normalize('בלחם'))).toBe(normalize('לחם'));
  });

  it('לא מקצץ מילים קצרות', () => {
    // "מלח" חייב להישאר מלח ולא להפוך ל"לח".
    expect(stripPrefix(normalize('מלח'))).toBeNull();
  });

  it('שומר את האסימון המקורי בין הווריאנטים', () => {
    const variants = tokenVariants(normalize('בלחם'));
    expect(variants).toContain(normalize('בלחם'));
    expect(variants).toContain(normalize('לחם'));
  });
});

describe('זיהוי סוג שאילתה', () => {
  it('מזהה ברקוד מלא', () => {
    expect(looksLikeBarcode(BAMBA)).toBe(true);
  });

  it('סובל מפרידים בתוך ברקוד', () => {
    expect(looksLikeBarcode('729 0000 066318')).toBe(true);
  });

  it('מחרוזת ספרות קצרה היא טקסט', () => {
    expect(looksLikeBarcode('1234')).toBe(false);
  });

  it('מחרוזת ספרות ארוכה מדי היא טקסט', () => {
    expect(looksLikeBarcode('1'.repeat(15))).toBe(false);
  });

  it('עברית היא טקסט', () => {
    expect(looksLikeBarcode('במבה')).toBe(false);
  });

  it('קלט מעורב הוא טקסט', () => {
    expect(looksLikeBarcode(`במבה ${BAMBA}`)).toBe(false);
  });

  it('משאיר ספרות בלבד בנרמול ברקוד', () => {
    expect(normalizeBarcode(' 729-0000 066318 ')).toBe(BAMBA);
  });
});

describe('בניית שאילתת FTS', () => {
  it('הופך כל אסימון להתאמת תחילית', () => {
    expect(toFtsQuery('במבה')).toBe(`"${normalize('במבה')}"*`);
  });

  it('דורש את כל האסימונים יחד', () => {
    expect(toFtsQuery('במבה אסם')).toContain(' AND ');
  });

  it('מחזיר ריק על קלט ריק', () => {
    expect(toFtsQuery('   ')).toBe('');
  });

  it('לא מאפשר הזרקת תחביר, כי הגרשיים נופלים בנרמול', () => {
    expect(toFtsQuery('במבה" OR "אסם')).not.toContain('OR');
  });
});
