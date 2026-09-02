/**
 * שער התנאים. חוסם את האפליקציה עד אישור, בכל כניסה.
 *
 * הכפתור נעול לחמש שניות ומראה ספירה לאחור, כדי שיהיה זמן קריאה בפועל
 * ולא רק הזדמנות ללחוץ. הספירה מוצגת כמספר ולא כאנימציה מעורפלת, כדי
 * שהמשתמש יידע כמה נשאר ולא ינסה ללחוץ שוב ושוב.
 */

import React, { useEffect, useRef, useState } from 'react';
import {
  AccessibilityInfo,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import {
  APP_NAME,
  TERMS_ACCEPT_LABEL,
  TERMS_BODY,
  TERMS_HEADLINE,
  TERMS_READ_SECONDS,
} from '../legal/copy';
import { color, radius, space, TOUCH_TARGET, typeScale } from '../theme';

interface Props {
  onAccept: () => void;
}

export function TermsScreen({ onAccept }: Props): React.ReactElement {
  const [secondsLeft, setSecondsLeft] = useState(TERMS_READ_SECONDS);
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    timer.current = setInterval(() => {
      setSecondsLeft((previous) => {
        if (previous <= 1 && timer.current) clearInterval(timer.current);
        return Math.max(0, previous - 1);
      });
    }, 1000);
    return () => {
      if (timer.current) clearInterval(timer.current);
    };
  }, []);

  useEffect(() => {
    if (secondsLeft === 0) {
      AccessibilityInfo.announceForAccessibility('אפשר לאשר ולהמשיך');
    }
  }, [secondsLeft]);

  const unlocked = secondsLeft === 0;

  return (
    <SafeAreaView style={styles.screen} edges={['top', 'bottom']}>
      <ScrollView
        contentContainerStyle={styles.content}
        showsVerticalScrollIndicator={false}
      >
        <Text style={styles.appName}>{APP_NAME}</Text>

        <View style={styles.headlineBlock}>
          <View style={styles.headlineRule} />
          <Text style={styles.headline}>{TERMS_HEADLINE}</Text>
        </View>

        <Text style={styles.body}>{TERMS_BODY}</Text>
      </ScrollView>

      <View style={styles.footer}>
        <Pressable
          accessibilityRole="button"
          accessibilityState={{ disabled: !unlocked }}
          accessibilityLabel={
            unlocked ? TERMS_ACCEPT_LABEL : `${TERMS_ACCEPT_LABEL}, זמין בעוד ${secondsLeft} שניות`
          }
          disabled={!unlocked}
          onPress={onAccept}
          style={({ pressed }) => [
            styles.button,
            !unlocked && styles.buttonLocked,
            pressed && unlocked && styles.buttonPressed,
          ]}
        >
          <Text style={[styles.buttonText, !unlocked && styles.buttonTextLocked]}>
            {unlocked ? TERMS_ACCEPT_LABEL : `${TERMS_ACCEPT_LABEL} · ${secondsLeft}`}
          </Text>
        </Pressable>
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  screen: {
    flex: 1,
    backgroundColor: color.ground,
  },
  content: {
    paddingHorizontal: space.xl,
    paddingTop: space.xxl,
    paddingBottom: space.xl,
  },
  appName: {
    ...typeScale.screenTitle,
    fontSize: 20,
    color: color.inkMuted,
    textAlign: 'right',
    writingDirection: 'rtl',
  },
  headlineBlock: {
    marginTop: space.xxl,
    marginBottom: space.xl,
  },
  headlineRule: {
    height: 4,
    width: 56,
    backgroundColor: color.alert,
    alignSelf: 'flex-end',
    marginBottom: space.md,
  },
  headline: {
    ...typeScale.screenTitle,
    fontSize: 30,
    lineHeight: 40,
    color: color.ink,
    textAlign: 'right',
    writingDirection: 'rtl',
  },
  body: {
    ...typeScale.body,
    color: color.ink,
    textAlign: 'right',
    writingDirection: 'rtl',
  },
  footer: {
    paddingHorizontal: space.xl,
    paddingTop: space.md,
    paddingBottom: space.md,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: color.rule,
    backgroundColor: color.surface,
  },
  button: {
    minHeight: TOUCH_TARGET,
    borderRadius: radius.control,
    backgroundColor: color.action,
    alignItems: 'center',
    justifyContent: 'center',
  },
  buttonLocked: {
    backgroundColor: color.rule,
  },
  buttonPressed: {
    backgroundColor: color.actionPressed,
  },
  buttonText: {
    ...typeScale.bodyStrong,
    color: color.onAction,
  },
  buttonTextLocked: {
    color: color.inkMuted,
  },
});
