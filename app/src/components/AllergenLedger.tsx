/**
 * טבלת האלרגנים של מוצר.
 *
 * מציגה את כל הרשימה הסגורה ולא רק את מה שידוע, כי השורות הריקות הן
 * המידע החשוב: הן מראות בדיוק מה לא בדקנו. אלרגן במצב "אין מידע" אינו
 * נעלם ואינו נדחק לסוף בשקט.
 *
 * סדר התצוגה: קודם מה שנמצא, אחר כך מה שלא ידוע, ולבסוף מה שהיצרן
 * הצהיר שאינו קיים. תת-סוגי אגוזים מוצגים רק כשיש עליהם מידע, כדי
 * שהטבלה לא תתפח לשמונה שורות ריקות בכל מוצר.
 */

import React from 'react';
import { StyleSheet, Text, View } from 'react-native';

import {
  TREE_NUTS_ID,
  labelOf,
  subtypesOf,
  topLevelAllergens,
} from '../domain/allergens';
import { AllergenMark, inkForLevel } from './AllergenMark';
import { LEVEL_LABEL, type AllergenLevels, type Level, levelOf } from '../domain/filter';
import { Rule } from './Panel';
import { color, space, typeScale } from '../theme';

const LEVEL_ORDER: Record<Level, number> = {
  contains: 0,
  may_contain: 1,
  unknown: 2,
  absent: 3,
};

interface Props {
  levels: AllergenLevels;
  /** אלרגנים שהמשתמש סינן. מודגשים בשורה כדי שיימצאו מיד. */
  highlighted?: ReadonlySet<string>;
}

interface Row {
  id: string;
  level: Level;
  isSubtype: boolean;
}

function buildRows(levels: AllergenLevels): Row[] {
  // ממיינים את אלרגני האב לפי מצב, ורק אז תולים על כל אחד את תת-הסוגים
  // הידועים שלו. כך תת-סוג נשאר צמוד לקבוצתו ואינו נודד בין המצבים.
  const parents = topLevelAllergens()
    .map((allergen) => ({
      id: allergen.id,
      level: levelOf(levels, allergen.id),
      isSubtype: false,
    }))
    .sort((first, second) => LEVEL_ORDER[first.level] - LEVEL_ORDER[second.level]);

  const rows: Row[] = [];
  for (const parent of parents) {
    rows.push(parent);
    if (parent.id !== TREE_NUTS_ID) continue;
    // תת-סוגים נכנסים רק כשיש עליהם מידע ממשי, אחרת כל מוצר יקבל שמונה
    // שורות ריקות של אגוזים.
    for (const subtype of subtypesOf(TREE_NUTS_ID)) {
      const level = levelOf(levels, subtype.id);
      if (level !== 'unknown') {
        rows.push({ id: subtype.id, level, isSubtype: true });
      }
    }
  }
  return rows;
}

export function AllergenLedger({ levels, highlighted }: Props): React.ReactElement {
  const rows = buildRows(levels);

  return (
    <View>
      {rows.map((row, index) => {
        const isHighlighted = highlighted?.has(row.id) ?? false;
        return (
          <View key={row.id}>
            {index > 0 ? <Rule /> : null}
            <View
              style={[styles.row, isHighlighted && styles.rowHighlighted]}
              accessibilityRole="text"
              accessibilityLabel={`${labelOf(row.id)}: ${LEVEL_LABEL[row.level]}`}
            >
              <AllergenMark level={row.level} />
              <Text
                style={[
                  styles.name,
                  row.isSubtype && styles.subtypeName,
                  row.level === 'unknown' && styles.mutedName,
                ]}
              >
                {labelOf(row.id)}
              </Text>
              <Text style={[styles.level, { color: inkForLevel(row.level) }]}>
                {LEVEL_LABEL[row.level]}
              </Text>
            </View>
          </View>
        );
      })}
    </View>
  );
}

const styles = StyleSheet.create({
  row: {
    flexDirection: 'row-reverse',
    alignItems: 'center',
    gap: space.md,
    paddingVertical: space.md,
  },
  rowHighlighted: {
    backgroundColor: color.actionSoft,
    marginHorizontal: -space.lg,
    paddingHorizontal: space.lg,
  },
  name: {
    ...typeScale.bodyStrong,
    color: color.ink,
    flex: 1,
    textAlign: 'right',
    writingDirection: 'rtl',
  },
  subtypeName: {
    ...typeScale.body,
    paddingRight: space.xl,
  },
  mutedName: {
    color: color.inkMuted,
  },
  level: {
    ...typeScale.label,
    textAlign: 'left',
    writingDirection: 'rtl',
  },
});
