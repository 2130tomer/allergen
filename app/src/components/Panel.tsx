/**
 * כרטיס תוכן.
 *
 * הגרסה הראשונה חיקתה תווית מזון: קווים דקים, פינות חדות, בלי צל.
 * הרעיון היה שהאפליקציה תיראה כמו הדבר שהיא מפנה אליו. בפועל זה יצא
 * שטוח, וקשה היה להבחין היכן נגמר פריט ומתחיל הבא, במיוחד ברשימה
 * ארוכה על מסך טלפון. הכרטיס המעוגל עם צל נמוך מפריד בלי להוסיף רעש.
 *
 * מה שנשמר מהגרסה הקודמת הוא האיפוק: אין גרדיאנטים, אין צבע דקורטיבי,
 * והצבע היחיד שנושא משמעות הוא צבע מצב האלרגן.
 */

import React from 'react';
import { StyleSheet, Text, View, ViewStyle } from 'react-native';

import { cardShadow, color, radius, space, typeScale } from '../theme';

interface PanelProps {
  title?: string;
  children: React.ReactNode;
  style?: ViewStyle;
}

export function Panel({ title, children, style }: PanelProps): React.ReactElement {
  return (
    <View style={[styles.panel, style]}>
      {title ? (
        <View style={styles.header}>
          <Text style={styles.title}>{title}</Text>
        </View>
      ) : null}
      <View style={styles.body}>{children}</View>
    </View>
  );
}

/** קו הפרדה דק בין שורות בתוך פאנל. */
export function Rule(): React.ReactElement {
  return <View style={styles.rule} />;
}

/** תווית סעיף קטנה ומרווחת, בנוסח פאנל תזונה. */
export function Eyebrow({ children }: { children: string }): React.ReactElement {
  return <Text style={styles.eyebrow}>{children}</Text>;
}

const styles = StyleSheet.create({
  panel: {
    backgroundColor: color.surface,
    borderRadius: radius.card,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: color.rule,
    marginHorizontal: space.md,
    marginBottom: space.md,
    overflow: 'hidden',
    ...cardShadow,
  },
  header: {
    paddingHorizontal: space.lg,
    paddingTop: space.md,
    paddingBottom: space.sm,
  },
  title: {
    ...typeScale.sectionTitle,
    color: color.ink,
    textAlign: 'right',
    writingDirection: 'rtl',
  },
  body: {
    paddingHorizontal: space.lg,
    paddingBottom: space.md,
  },
  rule: {
    height: StyleSheet.hairlineWidth,
    backgroundColor: color.rule,
  },
  eyebrow: {
    ...typeScale.sectionTitle,
    color: color.inkMuted,
    textAlign: 'right',
    writingDirection: 'rtl',
    marginBottom: space.sm,
  },
});
