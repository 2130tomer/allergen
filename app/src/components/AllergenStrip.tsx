/**
 * רצועת אלרגנים קומפקטית לשורה ברשימה.
 *
 * הרשימה היא המסך שרואים הכי הרבה, וללא הרצועה היא הציגה שם, יצרן
 * וברקוד בלבד — כלומר לא ענתה על השאלה היחידה שבגללה נפתחה
 * האפליקציה. הרצועה עונה עליה בלי לפתוח את המוצר.
 *
 * מוצג רק מה שנושא מידע: מה שנמצא במוצר ומה שהוצהר במפורש כלא קיים.
 * "אין מידע" אינו מקבל תווית לכל אלרגן בנפרד, כי ברשימה ארוכה זה היה
 * הופך לרעש שחוזר על עצמו בכל שורה. במקומו מוצגת שורה אחת מפורשת
 * כשאין על המוצר מידע כלל.
 *
 * המספר מוגבל, והשארית מוצגת כמונה. שורה ברשימה אינה תחליף למסך
 * המוצר, והיא לא אמורה להיראות כאילו היא ממצה את המידע.
 */

import React from 'react';
import { StyleSheet, Text, View } from 'react-native';

import { labelOf } from '../domain/allergens';
import { AllergenMark, inkForLevel } from './AllergenMark';
import type { AllergenLevels, Level } from '../domain/filter';
import { color, space, typeScale } from '../theme';

/** מעבר לזה השורה מתארכת ומאבדת את תפקידה כסריקה מהירה. */
const MAX_TAGS = 4;

const SHOWN: Level[] = ['contains', 'may_contain', 'absent'];
const ORDER: Record<string, number> = { contains: 0, may_contain: 1, absent: 2 };

interface Props {
  levels: AllergenLevels;
  /** אלרגנים שהמשתמש סינן. מוצגים ראשונים. */
  highlighted?: ReadonlySet<string>;
}

export function AllergenStrip({ levels, highlighted }: Props): React.ReactElement | null {
  const entries = Object.entries(levels)
    .filter(([, level]) => SHOWN.includes(level as Level))
    .sort((first, second) => {
      const firstPinned = highlighted?.has(first[0]) ? 0 : 1;
      const secondPinned = highlighted?.has(second[0]) ? 0 : 1;
      if (firstPinned !== secondPinned) return firstPinned - secondPinned;
      return ORDER[first[1]] - ORDER[second[1]];
    });

  if (entries.length === 0) return null;

  const shown = entries.slice(0, MAX_TAGS);
  const remaining = entries.length - shown.length;

  return (
    <View style={styles.strip}>
      {shown.map(([id, level]) => (
        <View key={id} style={styles.tag}>
          <AllergenMark level={level as Level} size={12} />
          <Text style={[styles.tagText, { color: inkForLevel(level as Level) }]}>
            {labelOf(id)}
          </Text>
        </View>
      ))}
      {remaining > 0 ? <Text style={styles.more}>{`+${remaining}`}</Text> : null}
    </View>
  );
}

const styles = StyleSheet.create({
  strip: {
    flexDirection: 'row-reverse',
    flexWrap: 'wrap',
    alignItems: 'center',
    gap: space.sm,
    marginTop: space.xs,
  },
  tag: {
    flexDirection: 'row-reverse',
    alignItems: 'center',
    gap: space.xs,
  },
  tagText: {
    ...typeScale.caption,
    fontSize: 12,
  },
  more: {
    ...typeScale.caption,
    fontSize: 12,
    color: color.inkFaint,
  },
});
