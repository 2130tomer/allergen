/**
 * טוקני העיצוב.
 *
 * שתי מגבלות מעצבות את הפלטה, ושתיהן נובעות מהחלטות מוצר ולא מטעם:
 *
 * 1. **ירוק מותר אך ורק להצהרת "ללא" מפורשת של היצרן.** ירוק נקרא
 *    כ"בטוח", ולכן הוא מותנה בטענה מוסדרת שמישהו נושא באחריות עליה —
 *    "ללא גלוטן" שמודפס על האריזה. הוא אסור באיסור מוחלט על היעדר
 *    מידע: מוצר שלא ידוע עליו דבר אינו ירוק, הוא אפור. הבחנה זו היא
 *    ההבדל בין אפליקציה בטוחה למסוכנת. ראו CONTEXT.md, מונחים אסורים.
 * 2. **אדום שמור אך ורק לאזהרות אלרגן.** לא לכפתורים, לא לכותרות, לא
 *    לקישוט. כשמופיע אדום על המסך, הוא תמיד אומר דבר אחד.
 * 3. **כיוון הממשק נקבע כאן ולא נגזר מהמכשיר.** ראו rtl בהמשך.
 *
 * צבע הפעולה הוא טורקיז כהה. הוא מופיע רק על פקדים ולעולם לא בתוך
 * טבלת האלרגנים, כדי שלא ייקרא בטעות כאישור.
 */

export const color = {
  /** רקע המסך. לבן קר עם נטייה כחלחלה, כמו תאורת מקרר בסופר. */
  ground: '#F2F4F5',
  /** משטח כרטיס או פאנל. */
  surface: '#FFFFFF',
  /** טקסט ראשי. שחור עם תת-גוון כחול. */
  ink: '#14181B',
  /** טקסט משני. */
  inkMuted: '#5A6B75',
  /** טקסט שלישוני, כיתובים משפטיים. */
  inkFaint: '#8A99A3',
  /** קווי הפרדה דקים, בסגנון פאנל תווית מזון. */
  rule: '#D6DEE2',
  ruleStrong: '#14181B',

  /** מכיל. אדום סימון, קרוב לאדום התווית האדומה הישראלית. */
  alert: '#C4262E',
  alertSoft: '#FBEDEE',
  /** עלול להכיל. ענבר, מוצג תמיד כקווקוו ולא כמילוי מלא. */
  caution: '#B26A00',
  cautionSoft: '#FBF3E6',
  /** אין מידע. אפור-פצל, תמיד בקו מקווקו. */
  unknown: '#5A6B75',
  unknownSoft: '#EDF1F3',
  /**
   * הוצהר "ללא". ירוק אשוח כהה, כהה דיו לניגודיות תקנית על לבן.
   * מותר להופיע רק כשקיימת הצהרה מפורשת על האריזה. ראו כלל 1 למעלה.
   */
  declaredFree: '#1B6B45',
  declaredFreeSoft: '#E8F2EC',

  /** צבע הפעולה. פקדים בלבד, לעולם לא סטטוס מוצר. */
  action: '#0E5C63',
  actionPressed: '#0A464B',
  actionSoft: '#E3EEEF',
  onAction: '#FFFFFF',

  /** רקע הפס המשפטי הקבוע. */
  warningBar: '#8E1B21',
  onWarningBar: '#FFF4F4',
} as const;

export const font = {
  /** תצוגה בלבד: שם האפליקציה וכותרות מסך. כבד ומאופק בשימוש. */
  display: 'SuezOne_400Regular',
  /** גוף וממשק. */
  body: 'Assistant_400Regular',
  bodyMedium: 'Assistant_600SemiBold',
  bodyBold: 'Assistant_700Bold',
  /** ברקודים, תאריכים ומספרים. הברקוד הוא זהות המוצר, ונראה ככזה. */
  mono: 'RobotoMono_400Regular',
} as const;

/**
 * כיוון הממשק.
 *
 * הגרסה הקודמת ניסתה לקבוע direction על מכל השורש. זו הייתה טעות:
 * direction אינו מאפיין סגנון תקף ב-React Native, והוא נדחה בזמן
 * ריצה. היישור שנראה תקין נבע כולו מ-textAlign.
 *
 * לכן הכיוון נשען על שני דברים שכן עובדים. הראשון הוא textAlign
 * ו-writingDirection, שמוחלים כאן כברירת מחדל על כל סולם הטיפוגרפיה
 * ולכן חלים על כל טקסט באפליקציה בלי שצריך לזכור אותם. השני הוא
 * row-reverse מפורש בכל שורה שסדר האיברים בה משמעותי.
 *
 * I18nManager.forceRTL נשאר קריאה נכונה ומועילה, אך אין להסתמך עליו
 * לבדו: באנדרואיד הוא תופס רק אחרי הפעלה מחדש של התהליך.
 */
export const rtl = {
  /** שורה שסדר האיברים בה משמעותי. */
  row: { flexDirection: 'row-reverse' },
  /** על טקסט. מיושם כברירת מחדל בכל typeScale. */
  text: { textAlign: 'right', writingDirection: 'rtl' },
} as const;

const rtlText = { textAlign: 'right', writingDirection: 'rtl' } as const;

export const typeScale = {
  screenTitle: { ...rtlText, fontFamily: font.display, fontSize: 26, lineHeight: 34 },
  sectionTitle: { ...rtlText, fontFamily: font.bodyBold, fontSize: 13, letterSpacing: 1.2 },
  productName: { ...rtlText, fontFamily: font.bodyBold, fontSize: 19, lineHeight: 26 },
  body: { ...rtlText, fontFamily: font.body, fontSize: 16, lineHeight: 24 },
  bodyStrong: { ...rtlText, fontFamily: font.bodyMedium, fontSize: 16, lineHeight: 24 },
  label: { ...rtlText, fontFamily: font.bodyMedium, fontSize: 14, lineHeight: 20 },
  caption: { ...rtlText, fontFamily: font.body, fontSize: 13, lineHeight: 19 },
  legal: { ...rtlText, fontFamily: font.body, fontSize: 12, lineHeight: 18 },
  barcode: { ...rtlText, fontFamily: font.mono, fontSize: 14, letterSpacing: 1.5 },
  data: { ...rtlText, fontFamily: font.mono, fontSize: 12, letterSpacing: 0.5 },
} as const;

export const space = {
  hair: 1,
  xs: 4,
  sm: 8,
  md: 12,
  lg: 16,
  xl: 24,
  xxl: 32,
} as const;

/** יעד נגיעה מינימלי. משתמשים באפליקציה ביד אחת, בעמידה, מול מדף. */
export const TOUCH_TARGET = 48;

export const radius = {
  /** פאנלים בסגנון תווית מזון אינם מעוגלים. */
  none: 0,
  control: 6,
  pill: 999,
} as const;
