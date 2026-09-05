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
  /** רקע המסך. אפור קריר ובהיר, שמפריד את הכרטיסים הלבנים מהמשטח. */
  ground: '#F6F7F9',
  /** משטח כרטיס או פאנל. */
  surface: '#FFFFFF',
  /** טקסט ראשי. */
  ink: '#0F172A',
  /** טקסט משני. */
  inkMuted: '#51607A',
  /** טקסט שלישוני, כיתובים משפטיים. */
  inkFaint: '#8494AB',
  /** קווי הפרדה דקים וגבול כרטיס. */
  rule: '#E4E8EF',
  ruleStrong: '#0F172A',

  /** מכיל. */
  alert: '#B91C1C',
  alertSoft: '#FEE2E2',
  /** עלול להכיל. ענבר, מוצג תמיד כקווקוו ולא כמילוי מלא. */
  caution: '#B45309',
  cautionSoft: '#FEF3C7',
  /** אין מידע. אפור-פצל, תמיד בקו מקווקו. */
  unknown: '#64748B',
  unknownSoft: '#F1F5F9',
  /**
   * הוצהר "ללא". ירוק, כהה דיו לניגודיות תקנית על לבן.
   * מותר להופיע רק כשקיימת הצהרה מפורשת על האריזה. ראו כלל 1 למעלה.
   */
  declaredFree: '#15803D',
  declaredFreeSoft: '#DCFCE7',

  /**
   * צבע הפעולה. פקדים בלבד, לעולם לא סטטוס מוצר.
   *
   * נשאר טורקיז נוטה לכחול ולא ירוק, גם כשמערכת העיצוב שממנה נלקחו
   * שאר הגוונים משתמשת בירוק-טורקיז כצבע מותג. ירוק על מסך הזה אומר
   * דבר אחד, "היצרן הצהיר ללא", וכפתור ירקרק היה מטשטש בדיוק את
   * ההבחנה שכל האפליקציה נשענת עליה.
   */
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
  none: 0,
  control: 10,
  /** כרטיס מוצר, פאנל, ותיבת מידע. */
  card: 16,
  pill: 999,
} as const;

/**
 * צל הכרטיס. רך ונמוך, ולא הצללה דרמטית.
 *
 * הגרסה הקודמת הייתה חסרת צל לגמרי ובנויה מקווי הפרדה, בסגנון פאנל
 * תווית מזון. זה היה עקבי אך שטוח, וקשה היה להבחין היכן נגמר מוצר
 * אחד ומתחיל הבא. הצל מפריד את הכרטיס מהרקע בלי להוסיף רעש.
 *
 * elevation הוא לאנדרואיד, ושאר המאפיינים ל-iOS ול-web.
 */
export const cardShadow = {
  shadowColor: '#0F172A',
  shadowOpacity: 0.07,
  shadowRadius: 12,
  shadowOffset: { width: 0, height: 2 },
  elevation: 2,
} as const;

/**
 * גלולת מצב אלרגן. מילוי רך עם טקסט כהה מאותה משפחת גוון.
 *
 * הזוגות מוגדרים כאן ולא בכל רכיב, כדי שהתאמה בין רמה לצבע תישאר
 * במקום אחד. שינוי כאן משנה את כל האפליקציה, וזה הרצוי: הצבע הוא
 * חלק מהמשמעות ולא קישוט.
 */
export const levelChip = {
  contains: { bg: color.alertSoft, fg: color.alert },
  may_contain: { bg: color.cautionSoft, fg: color.caution },
  absent: { bg: color.declaredFreeSoft, fg: color.declaredFree },
  unknown: { bg: color.unknownSoft, fg: color.unknown },
} as const;
