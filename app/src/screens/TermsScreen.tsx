/**
 * שער התנאים. חוסם את האפליקציה עד אישור, בכל כניסה.
 *
 * הכפתור נעול לזמן קצוב ומראה ספירה לאחור, כדי שיהיה זמן קריאה בפועל
 * ולא רק הזדמנות ללחוץ. הספירה מוצגת כמספר ולא כאנימציה מעורפלת, כדי
 * שהמשתמש יידע כמה נשאר ולא ינסה ללחוץ שוב ושוב.
 *
 * מספר הסעיף מוצג בתג נפרד ואינו חלק ממחרוזת הכותרת. הניסיון הקודם,
 * שבו הכותרת הייתה "1. מהות השירות", נראה שבור על מסך עברי: אלגוריתם
 * הדו-כיווניות מעביר את הנקודה לצד השני של המספר. הפרדה למרכיבים
 * פותרת את זה בלי תווי כיוון נסתרים בטקסט.
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
  TERMS_ACCEPT_NOTE,
  TERMS_HEADLINE,
  TERMS_LEAD,
  TERMS_READ_SECONDS,
  TERMS_SECTIONS,
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
        showsVerticalScrollIndicator={true}
      >
        <Text style={styles.appName}>{APP_NAME}</Text>

        <View style={styles.headlineBlock}>
          <View style={styles.headlineRule} />
          <Text style={styles.headline}>{TERMS_HEADLINE}</Text>
        </View>

        <View style={styles.leadCard}>
          <Text style={styles.leadText}>{TERMS_LEAD}</Text>
        </View>

        {TERMS_SECTIONS.map((section, index) => (
          <View key={section.title} style={styles.section}>
            <View style={styles.sectionHeader}>
              <View style={styles.badge}>
                <Text style={styles.badgeText}>{index + 1}</Text>
              </View>
              <Text style={styles.sectionTitle}>{stripNumber(section.title)}</Text>
            </View>
            <Text style={styles.sectionBody}>{section.body}</Text>
          </View>
        ))}
      </ScrollView>

      <View style={styles.footer}>
        <Text style={styles.acceptNote}>{TERMS_ACCEPT_NOTE}</Text>
        <Pressable
          accessibilityRole="button"
          accessibilityState={{ disabled: !unlocked }}
          accessibilityLabel={
            unlocked
              ? TERMS_ACCEPT_LABEL
              : `${TERMS_ACCEPT_LABEL}, זמין בעוד ${secondsLeft} שניות`
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

/** הכותרות במקור נושאות מספור; המספר מוצג בתג ולכן מוסר מהטקסט. */
function stripNumber(title: string): string {
  return title.replace(/^\s*\d+\.\s*/, '');
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
  },
  headlineBlock: {
    marginTop: space.xl,
    marginBottom: space.lg,
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
  },
  /** האזהרה המרכזית. היחידה על המסך שנושאת את האדום. */
  leadCard: {
    backgroundColor: color.alertSoft,
    borderRightWidth: 4,
    borderRightColor: color.alert,
    paddingVertical: space.lg,
    paddingHorizontal: space.lg,
    marginBottom: space.xl,
  },
  leadText: {
    ...typeScale.bodyStrong,
    color: color.ink,
  },
  section: {
    backgroundColor: color.surface,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: color.rule,
    padding: space.lg,
    marginBottom: space.md,
  },
  sectionHeader: {
    flexDirection: 'row-reverse',
    alignItems: 'center',
    gap: space.sm,
    marginBottom: space.sm,
  },
  badge: {
    width: 24,
    height: 24,
    borderRadius: radius.pill,
    backgroundColor: color.actionSoft,
    alignItems: 'center',
    justifyContent: 'center',
  },
  badgeText: {
    ...typeScale.label,
    textAlign: 'center',
    color: color.action,
  },
  sectionTitle: {
    ...typeScale.bodyStrong,
    color: color.ink,
    flex: 1,
  },
  sectionBody: {
    ...typeScale.body,
    color: color.inkMuted,
  },
  footer: {
    paddingHorizontal: space.xl,
    paddingTop: space.md,
    paddingBottom: space.md,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: color.rule,
    backgroundColor: color.surface,
  },
  acceptNote: {
    ...typeScale.legal,
    color: color.inkMuted,
    marginBottom: space.sm,
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
    textAlign: 'center',
    color: color.onAction,
  },
  buttonTextLocked: {
    color: color.inkMuted,
  },
});
