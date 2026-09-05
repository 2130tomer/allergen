/**
 * מסך המוצר. זהו רגע ההחלטה, ולכן כאן מרוכזות כל ההגנות.
 *
 * הפריסה בנויה כפאנל של תווית מזון: קווים דקים, תיבות, וסעיפים
 * מופרדים בקו ולא ברווח. האפליקציה שולחת את המשתמש לקרוא את האריזה,
 * וכדאי שהיא תיראה כמו הדבר שהיא מפנה אליו.
 *
 * הפס האדום בתחתית קבוע ואינו ניתן לסגירה.
 */

import React from 'react';
import { Image, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { AllergenLedger } from '../components/AllergenLedger';
import { Panel, Rule } from '../components/Panel';
import { WarningBar } from '../components/WarningBar';
import type { ProductDetail } from '../db/queries';
import { applyFilter } from '../domain/filter';
import {
  CONFLICT_TITLE,
  IMAGE_CAPTION_SHORT,
  IMAGE_DISCLAIMER,
  INGREDIENTS_KNOWN_NO_MATCH,
  NOT_A_FOOD_PRODUCT,
  NO_ALLERGEN_DATA,
  REPORT_INACCURACY_LABEL,
  collectedOn,
  imageCredit,
} from '../legal/copy';
import { useFilter } from '../state/FilterContext';
import { color, radius, space, TOUCH_TARGET, typeScale } from '../theme';

const SOURCE_LABEL: Record<string, string> = {
  manufacturer: 'אתר היצרן',
  declared_free_from: 'הצהרת "ללא" על האריזה',
  retailer: 'אתר הרשת',
  open_food_facts: 'Open Food Facts',
  label_extraction: 'חילוץ מתמונת תווית',
  user: 'דיווח משתמש',
};

interface Props {
  product: ProductDetail;
  onReportInaccuracy: (barcode: string) => void;
}

export function ProductScreen({ product, onReportInaccuracy }: Props): React.ReactElement {
  const { selection } = useFilter();
  const outcome = applyFilter(selection, product.levels);
  const highlighted = new Set([
    ...outcome.matchedAllergenIds,
    ...outcome.unknownAllergenIds,
  ]);

  return (
    <SafeAreaView style={styles.screen} edges={['top']}>
      <ScrollView contentContainerStyle={styles.content}>
        <View style={styles.header}>
          <Text style={styles.name}>{product.name}</Text>
          <Text style={styles.meta}>
            {[product.manufacturer, product.quantity && `${product.quantity} ${product.unit ?? ''}`.trim()]
              .filter(Boolean)
              .join(' · ')}
          </Text>
          <Text style={styles.barcode} accessibilityLabel={`ברקוד ${product.barcode}`}>
            {product.barcode}
          </Text>
        </View>

        {product.imageUrl ? (
          <View style={styles.imageBlock}>
            <Image
              source={{ uri: product.imageUrl }}
              style={styles.image}
              resizeMode="contain"
              accessibilityLabel={`תמונת ${product.name}, להמחשה בלבד`}
            />
            <Text style={styles.imageCaption}>{IMAGE_CAPTION_SHORT}</Text>
            {product.imageSource ? (
              <Text style={styles.imageCredit}>{imageCredit(product.imageSource)}</Text>
            ) : null}
          </View>
        ) : null}

        {product.conflicts.length > 0 ? (
          <View style={styles.conflict}>
            <Text style={styles.conflictTitle}>{CONFLICT_TITLE}</Text>
            {product.conflicts.map((message) => (
              <Text key={message} style={styles.conflictText}>
                {message}
              </Text>
            ))}
          </View>
        ) : null}

        {product.needsReview ? (
          <View style={styles.review}>
            <Text style={styles.reviewText}>
              המוצר הזה מסומן לבדיקה אצלנו. ייתכן שהמידע המוצג שייך למוצר קודם באותו
              ברקוד.
            </Text>
          </View>
        ) : null}

        <Panel title="אלרגנים">
          {product.departmentId === 'non_food' && !product.hasAllergenData ? (
            <Text style={styles.noData}>{NOT_A_FOOD_PRODUCT}</Text>
          ) : product.hasAllergenData ? (
            <AllergenLedger levels={product.levels} highlighted={highlighted} />
          ) : product.ingredientsKnown ? (
            /* שני מצבים שונים שנראו זהים עד כה. כאן יש בידינו רשימת
               רכיבים מלאה שלא אותר בה אלרגן, וזה נתון — לא היעדר נתון. */
            <Text style={styles.noData}>{INGREDIENTS_KNOWN_NO_MATCH}</Text>
          ) : (
            <Text style={styles.noData}>{NO_ALLERGEN_DATA}</Text>
          )}
        </Panel>

        <Panel title="מקור המידע">
          <Text style={styles.sourceLine}>
            {product.sources.length > 0
              ? product.sources.map((id) => SOURCE_LABEL[id] ?? id).join(' · ')
              : 'אין מקור רשום'}
          </Text>
          {product.allergensObservedOn ? (
            <>
              <Rule />
              <Text style={styles.sourceLine}>
                {collectedOn(formatDate(product.allergensObservedOn))}
              </Text>
            </>
          ) : null}
          {product.inferredAllergenIds.length > 0 ? (
            <>
              <Rule />
              <Text style={styles.inferredNote}>
                חלק מהרמות נגזרו מהצלבת רשימת האלרגנים של היצרן מול רשימת הרכיבים,
                כי היצרן פרסם אותן בלי הבחנה.
              </Text>
            </>
          ) : null}
          <Rule />
          <Text style={styles.legal}>{IMAGE_DISCLAIMER}</Text>
        </Panel>

        <Pressable
          accessibilityRole="button"
          onPress={() => onReportInaccuracy(product.barcode)}
          style={({ pressed }) => [styles.reportButton, pressed && styles.reportPressed]}
        >
          <Text style={styles.reportText}>{REPORT_INACCURACY_LABEL}</Text>
        </Pressable>
      </ScrollView>

      <WarningBar />
    </SafeAreaView>
  );
}

function formatDate(iso: string): string {
  const parsed = new Date(iso);
  if (Number.isNaN(parsed.getTime())) return iso;
  return parsed.toLocaleDateString('he-IL');
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: color.ground },
  content: { paddingBottom: space.xl },
  header: {
    backgroundColor: color.surface,
    paddingHorizontal: space.lg,
    paddingTop: space.lg,
    paddingBottom: space.md,
  },
  name: {
    ...typeScale.productName,
    color: color.ink,
    textAlign: 'right',
    writingDirection: 'rtl',
  },
  meta: {
    ...typeScale.caption,
    color: color.inkMuted,
    textAlign: 'right',
    writingDirection: 'rtl',
    marginTop: space.xs,
  },
  barcode: {
    ...typeScale.barcode,
    color: color.inkFaint,
    textAlign: 'right',
    marginTop: space.sm,
  },
  imageBlock: {
    backgroundColor: color.surface,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: color.rule,
    alignItems: 'center',
    paddingVertical: space.lg,
    paddingHorizontal: space.lg,
  },
  image: { width: 180, height: 180 },
  imageCaption: {
    ...typeScale.legal,
    color: color.inkMuted,
    marginTop: space.sm,
    textAlign: 'center',
    writingDirection: 'rtl',
  },
  imageCredit: {
    ...typeScale.legal,
    color: color.inkFaint,
    marginTop: space.xs,
    textAlign: 'center',
    writingDirection: 'rtl',
  },
  conflict: {
    backgroundColor: color.alertSoft,
    borderRightWidth: 4,
    borderRightColor: color.alert,
    padding: space.lg,
    marginTop: space.lg,
  },
  conflictTitle: {
    ...typeScale.bodyStrong,
    color: color.alert,
    textAlign: 'right',
    writingDirection: 'rtl',
    marginBottom: space.xs,
  },
  conflictText: {
    ...typeScale.caption,
    color: color.ink,
    textAlign: 'right',
    writingDirection: 'rtl',
  },
  review: {
    backgroundColor: color.cautionSoft,
    borderRightWidth: 4,
    borderRightColor: color.caution,
    padding: space.lg,
    marginTop: space.md,
  },
  reviewText: {
    ...typeScale.caption,
    color: color.ink,
    textAlign: 'right',
    writingDirection: 'rtl',
  },
  noData: {
    ...typeScale.body,
    color: color.unknown,
    textAlign: 'right',
    writingDirection: 'rtl',
    paddingVertical: space.md,
  },
  sourceLine: {
    ...typeScale.caption,
    color: color.ink,
    textAlign: 'right',
    writingDirection: 'rtl',
    paddingVertical: space.sm,
  },
  inferredNote: {
    ...typeScale.caption,
    color: color.inkMuted,
    textAlign: 'right',
    writingDirection: 'rtl',
    paddingVertical: space.sm,
  },
  legal: {
    ...typeScale.legal,
    color: color.inkFaint,
    textAlign: 'right',
    writingDirection: 'rtl',
    paddingTop: space.sm,
  },
  reportButton: {
    minHeight: TOUCH_TARGET,
    marginHorizontal: space.lg,
    marginTop: space.lg,
    borderRadius: radius.control,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: color.action,
    alignItems: 'center',
    justifyContent: 'center',
  },
  reportPressed: { backgroundColor: color.actionSoft },
  reportText: { ...typeScale.bodyStrong, color: color.action },
});
