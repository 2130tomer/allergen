/**
 * סריקת ברקוד.
 *
 * סדר החיפוש: המאגר המקומי, ואם אין, פנייה חיה ל-Open Food Facts כשיש
 * רשת, ואם גם זה נכשל, מסך "לא מצאנו" עם הצעה לצלם תווית.
 *
 * הצילום נכנס לתור לעיבוד ואינו מוצג למשתמש כתוצאה מיידית, כי חילוץ
 * אוטומטי לא אומת ואינו רשאי לקבוע שאלרגן נעדר. ראו ADR-0002.
 */

import { CameraView, useCameraPermissions } from 'expo-camera';
import React, { useCallback, useRef, useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { findByBarcode } from '../db/queries';
import { normalizeBarcode } from '../text/hebrew';
import { color, radius, space, TOUCH_TARGET, typeScale } from '../theme';

const ACCEPTED_TYPES = ['ean13', 'ean8', 'upc_a', 'upc_e', 'itf14'] as const;

/** מונע ריצה חוזרת על אותו ברקוד כשהמצלמה יורה פריימים ברצף. */
const RESCAN_COOLDOWN_MS = 1500;

interface Props {
  onFound: (barcode: string) => void;
  onNotFound: (barcode: string) => void;
}

export function ScannerScreen({ onFound, onNotFound }: Props): React.ReactElement {
  const [permission, requestPermission] = useCameraPermissions();
  const [isBusy, setIsBusy] = useState(false);
  const lastScan = useRef<{ code: string; at: number } | null>(null);

  const handleScan = useCallback(
    async ({ data }: { data: string }) => {
      const barcode = normalizeBarcode(data);
      if (!barcode || isBusy) return;

      const now = Date.now();
      const previous = lastScan.current;
      if (previous?.code === barcode && now - previous.at < RESCAN_COOLDOWN_MS) return;
      lastScan.current = { code: barcode, at: now };

      setIsBusy(true);
      try {
        const product = await findByBarcode(barcode);
        if (product) {
          onFound(barcode);
        } else {
          onNotFound(barcode);
        }
      } finally {
        setIsBusy(false);
      }
    },
    [isBusy, onFound, onNotFound],
  );

  if (!permission) {
    return <View style={styles.screen} />;
  }

  if (!permission.granted) {
    return (
      <SafeAreaView style={styles.screen}>
        <View style={styles.permission}>
          <Text style={styles.permissionTitle}>נדרשת גישה למצלמה</Text>
          <Text style={styles.permissionBody}>
            הסריקה קוראת את הברקוד מהאריזה. התמונה אינה נשמרת ואינה נשלחת לשום
            מקום.
          </Text>
          <Pressable
            accessibilityRole="button"
            onPress={requestPermission}
            style={styles.button}
          >
            <Text style={styles.buttonText}>אפשר גישה למצלמה</Text>
          </Pressable>
        </View>
      </SafeAreaView>
    );
  }

  return (
    <View style={styles.screen}>
      <CameraView
        style={StyleSheet.absoluteFill}
        facing="back"
        barcodeScannerSettings={{ barcodeTypes: [...ACCEPTED_TYPES] }}
        onBarcodeScanned={handleScan}
      />
      <SafeAreaView style={styles.overlay} pointerEvents="none">
        <View style={styles.reticle} />
        <Text style={styles.hint}>כוון את הברקוד למסגרת</Text>
      </SafeAreaView>
    </View>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: color.ink },
  overlay: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    gap: space.lg,
  },
  reticle: {
    width: '78%',
    height: 150,
    borderWidth: 3,
    borderColor: color.surface,
    borderRadius: radius.control,
  },
  hint: {
    ...typeScale.bodyStrong,
    color: color.surface,
    textAlign: 'center',
    writingDirection: 'rtl',
  },
  permission: {
    flex: 1,
    justifyContent: 'center',
    gap: space.lg,
    paddingHorizontal: space.xl,
    backgroundColor: color.ground,
  },
  permissionTitle: {
    ...typeScale.screenTitle,
    color: color.ink,
    textAlign: 'right',
    writingDirection: 'rtl',
  },
  permissionBody: {
    ...typeScale.body,
    color: color.inkMuted,
    textAlign: 'right',
    writingDirection: 'rtl',
  },
  button: {
    minHeight: TOUCH_TARGET,
    borderRadius: radius.control,
    backgroundColor: color.action,
    alignItems: 'center',
    justifyContent: 'center',
  },
  buttonText: { ...typeScale.bodyStrong, color: color.onAction },
});
