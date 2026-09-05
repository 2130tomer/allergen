/**
 * מסך הסינון: שתי רמות נפרדות ובלתי תלויות.
 *
 * הרמות מוצגות כשתי לשוניות ולא כרשימה אחת עם מתג חומרה, כי כך הן
 * באמת עובדות. אין כפתור "החמר בהכל" במכוון: מי שיש לו אלרגיה חמורה
 * לבוטנים ורגישות קלה ללקטוז צריך חומרה שונה לכל אחד מהם.
 *
 * רצועת הסיכום למעלה מציגה תמיד את שתי הרשימות יחד, גם כשעורכים רק
 * אחת מהן, כדי שהעצמאות ביניהן תהיה גלויה ולא מוסתרת מאחורי לשונית.
 */

import React, { useMemo, useState } from 'react';
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { labelOf, subtypesOf, topLevelAllergens } from '../domain/allergens';
import { gapWarnings } from '../domain/filter';
import { SelectionBox } from '../components/SelectionBox';
import { Eyebrow, Panel, Rule } from '../components/Panel';
import { useFilter } from '../state/FilterContext';
import { color, radius, space, TOUCH_TARGET, typeScale } from '../theme';

type Tab = 'contains' | 'mayContain';

const TAB_LABEL: Record<Tab, string> = {
  contains: 'מכיל',
  mayContain: 'עלול להכיל',
};

const TAB_EXPLANATION: Record<Tab, string> = {
  contains: 'הסתר מוצרים שהאלרגן הוא רכיב בהם.',
  mayContain: 'הסתר מוצרים שיש בהם סיכון לזיהום צולב בייצור.',
};

export function FilterScreen(): React.ReactElement {
  const { selection, toggleContains, toggleMayContain, clear } = useFilter();
  const [tab, setTab] = useState<Tab>('contains');
  // כל אלרגן-אב שיש לו תת-סוגים יכול להיפתח בנפרד. קודם היה כאן דגל
  // בודד לאגוזי עץ, וכשנוספו תת-סוגי דגן וקטניות הם נשארו בלי מרחיב.
  const [expanded, setExpanded] = useState<ReadonlySet<string>>(new Set());

  const active = tab === 'contains' ? selection.contains : selection.mayContain;
  const toggleActive = tab === 'contains' ? toggleContains : toggleMayContain;
  const warnings = useMemo(() => gapWarnings(selection), [selection]);

  const rows = topLevelAllergens();

  return (
    <SafeAreaView style={styles.screen} edges={['top']}>
      <ScrollView contentContainerStyle={styles.content}>
        <Text style={styles.title}>מה להסתיר</Text>

        <View style={styles.summary}>
          <SummaryLine label="מכיל" ids={[...selection.contains]} />
          <SummaryLine label="עלול להכיל" ids={[...selection.mayContain]} />
          {selection.contains.size + selection.mayContain.size > 0 ? (
            <Pressable
              accessibilityRole="button"
              onPress={clear}
              style={styles.clearButton}
            >
              <Text style={styles.clearText}>נקה הכל</Text>
            </Pressable>
          ) : null}
        </View>

        {warnings.map((warning) => (
          <View key={warning} style={styles.warning}>
            <Text style={styles.warningText}>{warning}</Text>
          </View>
        ))}

        <View style={styles.tabs} accessibilityRole="tablist">
          {(['contains', 'mayContain'] as Tab[]).map((candidate) => {
            const isActive = candidate === tab;
            return (
              <Pressable
                key={candidate}
                accessibilityRole="tab"
                accessibilityState={{ selected: isActive }}
                onPress={() => setTab(candidate)}
                style={[styles.tab, isActive && styles.tabActive]}
              >
                <Text style={[styles.tabText, isActive && styles.tabTextActive]}>
                  {TAB_LABEL[candidate]}
                </Text>
              </Pressable>
            );
          })}
        </View>

        <Panel>
          <Eyebrow>{TAB_EXPLANATION[tab]}</Eyebrow>
          {rows.map((allergen, index) => {
            const isSelected = active.has(allergen.id);
            const subtypes = subtypesOf(allergen.id);
            const isOpen = expanded.has(allergen.id);
            const toggleOpen = () =>
              setExpanded((current) => {
                const next = new Set(current);
                if (next.has(allergen.id)) next.delete(allergen.id);
                else next.add(allergen.id);
                return next;
              });
            return (
              <View key={allergen.id}>
                {index > 0 ? <Rule /> : null}
                <Pressable
                  accessibilityRole="checkbox"
                  accessibilityState={{ checked: isSelected }}
                  accessibilityLabel={`${labelOf(allergen.id)}, ${TAB_LABEL[tab]}`}
                  onPress={() => toggleActive(allergen.id)}
                  style={styles.row}
                >
                  <SelectionBox selected={isSelected} tone={tab} />
                  <Text style={[styles.rowLabel, isSelected && styles.rowLabelSelected]}>
                    {allergen.labelHe}
                  </Text>
                  {subtypes.length > 0 ? (
                    <Pressable
                      accessibilityRole="button"
                      accessibilityLabel={
                        isOpen
                          ? `סגור תת-סוגי ${allergen.labelHe}`
                          : `פתח תת-סוגי ${allergen.labelHe}`
                      }
                      hitSlop={12}
                      onPress={toggleOpen}
                    >
                      <Text style={styles.disclosure}>
                        {isOpen ? 'סגור' : 'לפי סוג'}
                      </Text>
                    </Pressable>
                  ) : null}
                </Pressable>

                {subtypes.length > 0 && isOpen
                  ? subtypes.map((subtype) => {
                      const subtypeSelected =
                        active.has(subtype.id) || active.has(allergen.id);
                      return (
                        <Pressable
                          key={subtype.id}
                          accessibilityRole="checkbox"
                          accessibilityState={{ checked: subtypeSelected }}
                          disabled={active.has(allergen.id)}
                          onPress={() => toggleActive(subtype.id)}
                          style={[styles.row, styles.subtypeRow]}
                        >
                          <SelectionBox selected={subtypeSelected} tone={tab} size={18} />
                          <Text style={styles.subtypeLabel}>{subtype.labelHe}</Text>
                        </Pressable>
                      );
                    })
                  : null}
              </View>
            );
          })}
        </Panel>

        {rows
          .filter(
            (allergen) =>
              active.has(allergen.id) &&
              expanded.has(allergen.id) &&
              subtypesOf(allergen.id).length > 0,
          )
          .map((allergen) => (
            <Text key={allergen.id} style={styles.note}>
              {`סימנת ${allergen.labelHe}, ולכן כל תת-הסוגים כלולים.`}
            </Text>
          ))}
      </ScrollView>
    </SafeAreaView>
  );
}

function SummaryLine({
  label,
  ids,
}: {
  label: string;
  ids: string[];
}): React.ReactElement {
  return (
    <View style={styles.summaryLine}>
      <Text style={styles.summaryLabel}>{label}</Text>
      <Text style={styles.summaryValue} numberOfLines={2}>
        {ids.length === 0 ? 'לא סומן דבר' : ids.map(labelOf).join(' · ')}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: color.ground },
  content: { paddingBottom: space.xxl },
  title: {
    ...typeScale.screenTitle,
    color: color.ink,
    textAlign: 'right',
    writingDirection: 'rtl',
    paddingHorizontal: space.lg,
    paddingTop: space.lg,
    paddingBottom: space.md,
  },
  summary: {
    backgroundColor: color.surface,
    paddingHorizontal: space.lg,
    paddingVertical: space.md,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderColor: color.rule,
    gap: space.xs,
  },
  summaryLine: { flexDirection: 'row-reverse', gap: space.sm },
  summaryLabel: {
    ...typeScale.label,
    color: color.inkMuted,
    width: 84,
    textAlign: 'right',
    writingDirection: 'rtl',
  },
  summaryValue: {
    ...typeScale.label,
    color: color.ink,
    flex: 1,
    textAlign: 'right',
    writingDirection: 'rtl',
  },
  clearButton: { alignSelf: 'flex-end', paddingVertical: space.xs },
  clearText: { ...typeScale.label, color: color.action },
  warning: {
    backgroundColor: color.cautionSoft,
    borderRightWidth: 4,
    borderRightColor: color.caution,
    paddingHorizontal: space.lg,
    paddingVertical: space.md,
    marginTop: space.md,
  },
  warningText: {
    ...typeScale.caption,
    color: color.ink,
    textAlign: 'right',
    writingDirection: 'rtl',
  },
  tabs: {
    flexDirection: 'row-reverse',
    gap: space.sm,
    paddingHorizontal: space.lg,
    paddingVertical: space.lg,
  },
  tab: {
    flex: 1,
    minHeight: TOUCH_TARGET,
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: radius.control,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: color.rule,
    backgroundColor: color.surface,
  },
  tabActive: { backgroundColor: color.action, borderColor: color.action },
  tabText: { ...typeScale.bodyStrong, color: color.inkMuted },
  tabTextActive: { color: color.onAction },
  row: {
    flexDirection: 'row-reverse',
    alignItems: 'center',
    gap: space.md,
    minHeight: TOUCH_TARGET,
  },
  subtypeRow: { paddingRight: space.xl, minHeight: 40 },
  rowLabel: {
    ...typeScale.body,
    color: color.ink,
    flex: 1,
    textAlign: 'right',
    writingDirection: 'rtl',
  },
  rowLabelSelected: { ...typeScale.bodyStrong },
  subtypeLabel: {
    ...typeScale.caption,
    color: color.inkMuted,
    flex: 1,
    textAlign: 'right',
    writingDirection: 'rtl',
  },
  disclosure: { ...typeScale.caption, color: color.action },
  note: {
    ...typeScale.caption,
    color: color.inkMuted,
    paddingHorizontal: space.lg,
    paddingTop: space.md,
    textAlign: 'right',
    writingDirection: 'rtl',
  },
});
