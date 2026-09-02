/**
 * פאנל בסגנון תווית מזון.
 *
 * המסכים בנויים מקווים דקים ותיבות ולא מכרטיסים מרחפים עם צל. זה לא
 * טעם: האפליקציה אומרת למשתמש ללכת לקרוא את התווית על האריזה, וכדאי
 * שהיא תיראה כמו הדבר שהיא מפנה אליו.
 */

import React from 'react';
import { StyleSheet, Text, View, ViewStyle } from 'react-native';

import { color, space, typeScale } from '../theme';

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
    borderTopWidth: 2,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderColor: color.ruleStrong,
    borderBottomColor: color.rule,
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
