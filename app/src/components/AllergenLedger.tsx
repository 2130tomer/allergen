/**
 * טבלת האלרגנים של מוצר.
 *
 * הטבלה מחולקת לשלושה בלוקים מוצהרים: מה שנמצא במוצר, מה שהוצהר
 * במפורש כלא קיים, ומה שאין עליו מידע.
 *
 * החלוקה נולדה מבעיה מדידה. כשרשימת האלרגנים גדלה לארבעים ושניים,
 * מוצר טיפוסי ייצר עשרים וחמש שורות רצופות של "אין מידע", והן הטביעו
 * את השורות שנושאות מידע ממשי. שורה ירוקה של הצהרת "ללא" נדחקה אל
 * מתחת לקיפול המסך.
 *
 * הפתרון אינו הסתרה. בלוק "אין מידע" מקובץ לשורה אחת שנושאת מונה
 * מפורש וניתנת לפתיחה, כך שהעובדה שאיננו יודעים נשארת אמירה בולטת
 * ולא היעדר שקט. זו הנקודה שבה אפליקציות אחרות פשוט לא מציגות כלום,
 * ואצלנו אסור שהיעדר מידע ייראה כמו היעדר אלרגן.
 *
 * תת-סוגים — אגוזים, דגנים וקטניות — מוצגים רק כשיש עליהם מידע.
 */

import React, { useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { labelOf, subtypesOf, topLevelAllergens } from '../domain/allergens';
import { AllergenMark, inkForLevel } from './AllergenMark';
import { LEVEL_LABEL, type AllergenLevels, type Level, levelOf } from '../domain/filter';
import { DECLARED_FREE_NOTE } from '../legal/copy';
import { Rule } from './Panel';
import { color, space, TOUCH_TARGET, typeScale } from '../theme';

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

const PRESENT_ORDER: Record<string, number> = { contains: 0, may_contain: 1 };

function buildRows(levels: AllergenLevels): Row[] {
  const rows: Row[] = [];
  for (const allergen of topLevelAllergens()) {
    rows.push({ id: allergen.id, level: levelOf(levels, allergen.id), isSubtype: false });
    for (const subtype of subtypesOf(allergen.id)) {
      const level = levelOf(levels, subtype.id);
      if (level !== 'unknown') {
        rows.push({ id: subtype.id, level, isSubtype: true });
      }
    }
  }
  return rows;
}

function LedgerRow({
  row,
  highlighted,
}: {
  row: Row;
  highlighted: boolean;
}): React.ReactElement {
  return (
    <View
      style={[styles.row, highlighted && styles.rowHighlighted]}
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
  );
}

function Block({
  title,
  rows,
  highlighted,
  note,
}: {
  title: string;
  rows: Row[];
  highlighted?: ReadonlySet<string>;
  note?: string;
}): React.ReactElement | null {
  if (rows.length === 0) return null;
  return (
    <View style={styles.block}>
      <Text style={styles.blockTitle}>{title}</Text>
      {note ? <Text style={styles.blockNote}>{note}</Text> : null}
      {rows.map((row, index) => (
        <View key={row.id}>
          {index > 0 ? <Rule /> : null}
          <LedgerRow row={row} highlighted={highlighted?.has(row.id) ?? false} />
        </View>
      ))}
    </View>
  );
}

export function AllergenLedger({ levels, highlighted }: Props): React.ReactElement {
  const [unknownOpen, setUnknownOpen] = useState(false);
  const rows = buildRows(levels);

  const present = rows
    .filter((row) => row.level === 'contains' || row.level === 'may_contain')
    .sort((first, second) => PRESENT_ORDER[first.level] - PRESENT_ORDER[second.level]);
  const declaredFree = rows.filter((row) => row.level === 'absent');
  const unknown = rows.filter((row) => row.level === 'unknown');

  return (
    <View>
      <Block title="נמצא במוצר" rows={present} highlighted={highlighted} />
      <Block
        title={'הוצהר "ללא" על האריזה'}
        rows={declaredFree}
        highlighted={highlighted}
        note={DECLARED_FREE_NOTE}
      />

      {unknown.length > 0 ? (
        <View style={styles.block}>
          <Pressable
            accessibilityRole="button"
            accessibilityState={{ expanded: unknownOpen }}
            accessibilityLabel={`אין מידע על ${unknown.length} אלרגנים. ${
              unknownOpen ? 'סגור רשימה' : 'פתח רשימה'
            }`}
            onPress={() => setUnknownOpen((open) => !open)}
            style={styles.unknownHeader}
          >
            <AllergenMark level="unknown" />
            <Text style={styles.unknownText}>
              {`אין לנו מידע על ${unknown.length} אלרגנים נוספים`}
            </Text>
            <Text style={styles.unknownToggle}>{unknownOpen ? 'סגירה' : 'הצגה'}</Text>
          </Pressable>

          {unknownOpen
            ? unknown.map((row) => (
                <View key={row.id}>
                  <Rule />
                  <LedgerRow row={row} highlighted={highlighted?.has(row.id) ?? false} />
                </View>
              ))
            : null}
        </View>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  block: {
    marginBottom: space.lg,
  },
  blockTitle: {
    ...typeScale.sectionTitle,
    color: color.inkMuted,
    marginBottom: space.xs,
  },
  blockNote: {
    ...typeScale.legal,
    color: color.inkFaint,
    marginBottom: space.xs,
  },
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
  },
  /** בולט במכוון. היעדר מידע הוא אמירה, לא שתיקה. */
  unknownHeader: {
    flexDirection: 'row-reverse',
    alignItems: 'center',
    gap: space.md,
    minHeight: TOUCH_TARGET,
    paddingHorizontal: space.md,
    backgroundColor: color.unknownSoft,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: color.unknown,
  },
  unknownText: {
    ...typeScale.bodyStrong,
    color: color.ink,
    flex: 1,
  },
  unknownToggle: {
    ...typeScale.label,
    textAlign: 'left',
    color: color.action,
  },
});
