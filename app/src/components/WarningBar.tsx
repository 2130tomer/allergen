/**
 * הפס המשפטי הקבוע.
 *
 * יושב בתחתית המסך ולא בראשו, משתי סיבות: שם הוא באזור האגודל ובסוף
 * מסלול הקריאה של טבלת האלרגנים, ושם אי אפשר לגלול מעליו. אין לו כפתור
 * סגירה. הוא מופיע במסך המוצר ובתוצאת הסריקה, כלומר ברגע ההחלטה עצמו.
 */

import React from 'react';
import { StyleSheet, Text, View } from 'react-native';

import { PERSISTENT_WARNING } from '../legal/copy';
import { color, space, typeScale } from '../theme';

export function WarningBar(): React.ReactElement {
  return (
    <View
      style={styles.bar}
      accessibilityRole="alert"
      accessibilityLabel={PERSISTENT_WARNING}
    >
      <Text style={styles.mark}>!</Text>
      <Text style={styles.text}>{PERSISTENT_WARNING}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  bar: {
    flexDirection: 'row-reverse',
    alignItems: 'center',
    gap: space.md,
    backgroundColor: color.warningBar,
    paddingHorizontal: space.lg,
    paddingTop: space.md,
    paddingBottom: space.lg,
  },
  mark: {
    ...typeScale.bodyStrong,
    color: color.warningBar,
    backgroundColor: color.onWarningBar,
    width: 24,
    height: 24,
    borderRadius: 12,
    textAlign: 'center',
    lineHeight: 24,
    overflow: 'hidden',
  },
  text: {
    ...typeScale.caption,
    color: color.onWarningBar,
    flex: 1,
    textAlign: 'right',
    writingDirection: 'rtl',
  },
});
