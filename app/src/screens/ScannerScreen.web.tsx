/**
 * אין מצלמה בבנייה ל-web. המסך אומר זאת במפורש במקום להיראות שבור.
 */

import React from 'react';
import { StyleSheet, Text, View } from 'react-native';

import { color, space, typeScale } from '../theme';

interface Props {
  onFound: (barcode: string) => void;
  onNotFound: (barcode: string) => void;
}

export function ScannerScreen(_props: Props): React.ReactElement {
  return (
    <View style={styles.screen}>
      <Text style={styles.title}>סריקה זמינה באפליקציה בלבד</Text>
      <Text style={styles.body}>
        הבנייה לדפדפן משמשת לבדיקת הממשק. סריקת ברקוד דורשת מצלמה ורצה על
        המכשיר.
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  screen: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    gap: space.md,
    paddingHorizontal: space.xl,
    backgroundColor: color.ground,
  },
  title: {
    ...typeScale.screenTitle,
    color: color.ink,
    textAlign: 'center',
    writingDirection: 'rtl',
  },
  body: {
    ...typeScale.body,
    color: color.inkMuted,
    textAlign: 'center',
    writingDirection: 'rtl',
  },
});
