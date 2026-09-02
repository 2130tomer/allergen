/**
 * בדיקות הסינון בצד הלקוח.
 *
 * מקבילות ל-TestFiltering ב-pipeline/tests/test_domain.py. הסינון מחושב
 * פעמיים במערכת — פעם בשרת כשבונים דוחות ופעם במכשיר בזמן אמת — ושתי
 * המימושים חייבים להסכים.
 */

import { TREE_NUTS_ID, expandSelection } from '../src/domain/allergens';
import {
  EMPTY_SELECTION,
  applyFilter,
  deserialize,
  gapWarnings,
  isEmptySelection,
  serialize,
  toggle,
  type AllergenLevels,
  type FilterSelection,
} from '../src/domain/filter';

const bamba: AllergenLevels = { peanuts: 'contains', soy: 'may_contain' };
const noData: AllergenLevels = {};

function selection(
  contains: string[] = [],
  mayContain: string[] = [],
): FilterSelection {
  return { contains: new Set(contains), mayContain: new Set(mayContain) };
}

describe('היררכיית אגוזים', () => {
  it('בחירת אגוזי עץ תופסת את כל תת-הסוגים', () => {
    const expanded = expandSelection([TREE_NUTS_ID]);
    expect(expanded.has('cashew')).toBe(true);
    expect(expanded.has(TREE_NUTS_ID)).toBe(true);
  });

  it('בחירת קשיו אינה תופסת אגוזים אחרים', () => {
    expect([...expandSelection(['cashew'])]).toEqual(['cashew']);
  });
});

describe('סינון', () => {
  it('בחירה ריקה מציגה הכל', () => {
    expect(applyFilter(EMPTY_SELECTION, bamba).visibility).toBe('visible');
    expect(isEmptySelection(EMPTY_SELECTION)).toBe(true);
  });

  it('רשימת מכיל מסתירה מוצר מתאים', () => {
    const outcome = applyFilter(selection(['peanuts']), bamba);
    expect(outcome.visibility).toBe('hidden');
    expect(outcome.matchedAllergenIds).toEqual(['peanuts']);
  });

  it('רשימת עלול להכיל מסתירה מוצר מתאים', () => {
    expect(applyFilter(selection([], ['soy']), bamba).visibility).toBe('hidden');
  });

  it('שתי הרשימות עצמאיות: סימון סויה במכיל אינו מסתיר עלול להכיל', () => {
    expect(applyFilter(selection(['soy']), bamba).visibility).toBe('visible');
  });

  it('סימון בעלול להכיל בלבד עדיין מציג מוצר שמכיל', () => {
    expect(applyFilter(selection([], ['peanuts']), bamba).visibility).toBe('visible');
  });

  it('הפער הזה מייצר אזהרה מפורשת', () => {
    const warnings = gapWarnings(selection([], ['peanuts']));
    expect(warnings).toHaveLength(1);
    expect(warnings[0]).toContain('בוטנים');
  });

  it('אין אזהרה כששתי הרשימות מסכימות', () => {
    expect(gapWarnings(selection(['peanuts'], ['peanuts']))).toEqual([]);
  });

  it('מוצר בלי מידע נופל לסעיף אין מידע', () => {
    const outcome = applyFilter(selection(['milk']), noData);
    expect(outcome.visibility).toBe('unknown');
    expect(outcome.unknownAllergenIds).toEqual(['milk']);
  });

  it('היעדר אלרגן ידוע נחשב מידע ומציג את המוצר', () => {
    expect(applyFilter(selection(['milk']), { milk: 'absent' }).visibility).toBe(
      'visible',
    );
  });

  it('בחירת אגוזי עץ מסתירה מוצר עם קשיו', () => {
    const outcome = applyFilter(selection([TREE_NUTS_ID]), { cashew: 'contains' });
    expect(outcome.visibility).toBe('hidden');
  });

  it('מידע על תת-סוג נחשב מידע על הקבוצה', () => {
    const outcome = applyFilter(selection([TREE_NUTS_ID]), { cashew: 'absent' });
    expect(outcome.visibility).toBe('visible');
  });
});

describe('החסנת הבחירה', () => {
  it('הלוך ושוב שומר על שתי הרשימות', () => {
    const original = selection(['peanuts'], ['soy']);
    const restored = deserialize(serialize(original));
    expect([...restored.contains]).toEqual(['peanuts']);
    expect([...restored.mayContain]).toEqual(['soy']);
  });

  it('החסנה חסרה נקראת כבחירה ריקה', () => {
    expect(isEmptySelection(deserialize(null))).toBe(true);
  });

  it('החלפה מוסיפה ומסירה', () => {
    const once = toggle(new Set<string>(), 'milk');
    expect(once.has('milk')).toBe(true);
    expect(toggle(once, 'milk').has('milk')).toBe(false);
  });
});
