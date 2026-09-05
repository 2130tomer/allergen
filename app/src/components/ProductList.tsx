/**
 * רשימת מוצרים מסוננת, מחולקת לשתי קבוצות תצוגה.
 *
 * מוצרי "אין מידע" יושבים בסעיף נפרד בתחתית ולא מעורבבים ברשימה
 * הראשית. הם גם לא נעלמים בשקט: מוצר שאיננו יודעים עליו הוא בדיוק
 * המוצר שהמשתמש צריך לבדוק על האריזה.
 *
 * מספר המוצרים שהוסתרו מוצג במפורש, כדי שהמשתמש ידע שהסינון עובד ולא
 * יחשוב שהקטלוג ריק.
 */

import React, { useMemo, useState } from 'react';
import { Image, Pressable, SectionList, StyleSheet, Text, View } from 'react-native';

import { AllergenMark } from './AllergenMark';
import { AllergenStrip } from './AllergenStrip';
import type { ProductSummary } from '../db/queries';
import {
  applyFilter,
  selectedIds,
  type AllergenLevels,
  type FilterSelection,
} from '../domain/filter';
import { labelOf } from '../domain/allergens';
import {
  FILTER_RESULT_HEADER,
  UNKNOWN_SECTION_SUBTITLE,
  UNKNOWN_SECTION_TITLE,
} from '../legal/copy';
import { color, space, TOUCH_TARGET, typeScale } from '../theme';

interface Props {
  products: ProductSummary[];
  levelsByBarcode: Record<string, AllergenLevels>;
  selection: FilterSelection;
  onSelect: (barcode: string) => void;
  emptyMessage?: string;
}

interface Item {
  product: ProductSummary;
  unknownAllergenIds: string[];
}

/**
 * שורת המשנה: יצרן וברקוד.
 *
 * בקבצי שקיפות המחירים שדה היצרן נושא לעיתים את שם המוצר עצמו, ואז
 * השורה חזרה על הכותרת מילה במילה. במקרה כזה מוצג הברקוד בלבד.
 */
function metaLine(product: ProductSummary): string {
  const manufacturer = product.manufacturer?.trim();
  const isEcho = !manufacturer || manufacturer === product.name.trim();
  return isEcho ? product.barcode : `${manufacturer} · ${product.barcode}`;
}

export function ProductList({
  products,
  levelsByBarcode,
  selection,
  onSelect,
  emptyMessage = 'אין מוצרים להצגה.',
}: Props): React.ReactElement {
  const [unknownOpen, setUnknownOpen] = useState(false);

  // מה שהמשתמש סינן נדחף לראש הרצועה, כדי שיימצא בלי קריאה של כולה.
  const highlightedIds = useMemo(() => selectedIds(selection), [selection]);

  const { visible, unknown, hiddenCount } = useMemo(() => {
    const visibleItems: Item[] = [];
    const unknownItems: Item[] = [];
    let hidden = 0;

    for (const product of products) {
      const levels = levelsByBarcode[product.barcode] ?? {};
      const outcome = applyFilter(selection, levels);
      if (outcome.visibility === 'visible') {
        visibleItems.push({ product, unknownAllergenIds: [] });
      } else if (outcome.visibility === 'unknown') {
        unknownItems.push({ product, unknownAllergenIds: outcome.unknownAllergenIds });
      } else {
        hidden += 1;
      }
    }
    return { visible: visibleItems, unknown: unknownItems, hiddenCount: hidden };
  }, [products, levelsByBarcode, selection]);

  const sections = [
    { key: 'visible', title: null as string | null, data: visible },
    {
      key: 'unknown',
      title: UNKNOWN_SECTION_TITLE,
      data: unknownOpen ? unknown : [],
    },
  ].filter((section) => section.key === 'visible' || unknown.length > 0);

  return (
    <SectionList
      sections={sections}
      keyExtractor={(item) => item.product.barcode}
      stickySectionHeadersEnabled={false}
      contentContainerStyle={styles.content}
      ListHeaderComponent={
        <View style={styles.listHeader}>
          <Text style={styles.disclaimer}>{FILTER_RESULT_HEADER}</Text>
          {hiddenCount > 0 ? (
            <Text style={styles.hiddenCount}>
              {hiddenCount} מוצרים הוסתרו לפי הסינון שלך
            </Text>
          ) : null}
        </View>
      }
      ListEmptyComponent={<Text style={styles.empty}>{emptyMessage}</Text>}
      renderSectionHeader={({ section }) =>
        section.title ? (
          <Pressable
            accessibilityRole="button"
            accessibilityState={{ expanded: unknownOpen }}
            onPress={() => setUnknownOpen((open) => !open)}
            style={styles.unknownHeader}
          >
            <View style={styles.unknownHeaderRow}>
              <AllergenMark level="unknown" size={18} />
              <Text style={styles.unknownTitle}>
                {section.title} ({unknown.length})
              </Text>
              <Text style={styles.disclosure}>{unknownOpen ? 'סגור' : 'הצג'}</Text>
            </View>
            {unknownOpen ? (
              <Text style={styles.unknownSubtitle}>{UNKNOWN_SECTION_SUBTITLE}</Text>
            ) : null}
          </Pressable>
        ) : null
      }
      renderItem={({ item }) => (
        <Pressable
          accessibilityRole="button"
          onPress={() => onSelect(item.product.barcode)}
          style={({ pressed }) => [styles.row, pressed && styles.rowPressed]}
        >
          <View style={styles.thumb}>
            {item.product.imageUrl ? (
              <Image
                source={{ uri: item.product.imageUrl }}
                style={styles.thumbImage}
                resizeMode="contain"
                accessible={false}
              />
            ) : (
              <Text style={styles.thumbEmpty}>אין תמונה</Text>
            )}
          </View>

          <View style={styles.rowText}>
            <Text style={styles.rowName} numberOfLines={2}>
              {item.product.name}
            </Text>
            <Text style={styles.rowMeta} numberOfLines={1}>
              {metaLine(item.product)}
            </Text>

            <AllergenStrip
              levels={levelsByBarcode[item.product.barcode] ?? {}}
              highlighted={highlightedIds}
            />

            {!item.product.hasAllergenData ? (
              <View style={styles.noDataRow}>
                <AllergenMark level="unknown" size={12} />
                <Text style={styles.rowUnknown}>אין לנו מידע אלרגנים על מוצר זה</Text>
              </View>
            ) : null}

            {item.unknownAllergenIds.length > 0 ? (
              <Text style={styles.rowUnknown}>
                אין מידע על {item.unknownAllergenIds.map(labelOf).join(', ')}
              </Text>
            ) : null}
          </View>
        </Pressable>
      )}
    />
  );
}

const styles = StyleSheet.create({
  content: { paddingBottom: space.xxl },
  listHeader: {
    paddingHorizontal: space.lg,
    paddingVertical: space.md,
    backgroundColor: color.ground,
  },
  disclaimer: {
    ...typeScale.legal,
    color: color.inkMuted,
    textAlign: 'right',
    writingDirection: 'rtl',
  },
  hiddenCount: {
    ...typeScale.caption,
    color: color.ink,
    textAlign: 'right',
    writingDirection: 'rtl',
    marginTop: space.xs,
  },
  row: {
    flexDirection: 'row-reverse',
    alignItems: 'center',
    gap: space.md,
    minHeight: TOUCH_TARGET + 8,
    paddingHorizontal: space.lg,
    paddingVertical: space.md,
    backgroundColor: color.surface,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: color.rule,
  },
  rowPressed: { backgroundColor: color.actionSoft },
  rowText: { flex: 1 },
  thumb: {
    width: 52,
    height: 52,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: color.rule,
    backgroundColor: color.ground,
    alignItems: 'center',
    justifyContent: 'center',
  },
  thumbImage: { width: '100%', height: '100%' },
  thumbEmpty: {
    ...typeScale.legal,
    fontSize: 9,
    textAlign: 'center',
    color: color.inkFaint,
  },
  noDataRow: {
    flexDirection: 'row-reverse',
    alignItems: 'center',
    gap: space.xs,
    marginTop: space.xs,
  },
  rowName: {
    ...typeScale.bodyStrong,
    color: color.ink,
    textAlign: 'right',
    writingDirection: 'rtl',
  },
  rowMeta: {
    ...typeScale.data,
    color: color.inkFaint,
    textAlign: 'right',
    marginTop: space.xs,
  },
  rowUnknown: {
    ...typeScale.caption,
    color: color.unknown,
    textAlign: 'right',
    writingDirection: 'rtl',
    marginTop: space.xs,
  },
  unknownHeader: {
    backgroundColor: color.unknownSoft,
    paddingHorizontal: space.lg,
    paddingVertical: space.md,
    borderTopWidth: 2,
    borderTopColor: color.unknown,
    marginTop: space.lg,
  },
  unknownHeaderRow: {
    flexDirection: 'row-reverse',
    alignItems: 'center',
    gap: space.sm,
  },
  unknownTitle: {
    ...typeScale.bodyStrong,
    color: color.ink,
    flex: 1,
    textAlign: 'right',
    writingDirection: 'rtl',
  },
  unknownSubtitle: {
    ...typeScale.caption,
    color: color.inkMuted,
    textAlign: 'right',
    writingDirection: 'rtl',
    marginTop: space.xs,
  },
  disclosure: { ...typeScale.label, color: color.action },
  empty: {
    ...typeScale.body,
    color: color.inkMuted,
    textAlign: 'center',
    padding: space.xxl,
  },
});
