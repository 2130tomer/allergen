/** Loads local data first, distinguishes outages, and opens user-submitted report drafts. */

import type { NativeStackScreenProps } from '@react-navigation/native-stack';
import React, { useEffect, useState } from 'react';
import { ActivityIndicator, Alert, Linking, Pressable, StyleSheet, Text, View } from 'react-native';

import type { RootStackParamList } from '../../App';
import { WarningBar } from '../components/WarningBar';
import { loadProduct, type ProductDetail } from '../db/queries';
import { fetchFromOpenFoodFacts, ProductLookupError } from '../net/openFoodFacts';
import { ProductScreen } from './ProductScreen';
import { color, radius, space, TOUCH_TARGET, typeScale } from '../theme';

type Props = NativeStackScreenProps<RootStackParamList, 'Product'>;

type State =
  | { kind: 'loading' }
  | { kind: 'ready'; product: ProductDetail }
  | { kind: 'missing'; barcode: string }
  | { kind: 'error'; message: string };

export function ProductScreenContainer({ route }: Props): React.ReactElement {
  const { barcode } = route.params;
  const [state, setState] = useState<State>({ kind: 'loading' });
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let cancelled = false;
    setState({ kind: 'loading' });

    (async () => {
      const local = await loadProduct(barcode);
      if (cancelled) return;
      if (local) {
        setState({ kind: 'ready', product: local });
        return;
      }

      const remote = await fetchFromOpenFoodFacts(barcode);
      if (cancelled) return;
      setState(
        remote
          ? { kind: 'ready', product: remote }
          : { kind: 'missing', barcode },
      );
    })().catch((error) => {
      if (!cancelled) setState({ kind: 'error', message: error instanceof ProductLookupError
        ? 'לא ניתן לבדוק את המוצר במקור המקוון כרגע. נסה שוב כשיש חיבור.'
        : 'אירעה שגיאה בטעינת המאגר המקומי. לא ניתן לקבוע אם המוצר קיים.' });
    });

    return () => {
      cancelled = true;
    };
  }, [barcode, attempt]);

  if (state.kind === 'loading') {
    return (
      <View style={styles.centered}>
        <ActivityIndicator color={color.action} />
      </View>
    );
  }

  if (state.kind === 'error') {
    return <View style={styles.centered}>
      <Text style={styles.missingBody}>{state.message}</Text>
      <Pressable accessibilityRole="button" style={styles.button} onPress={() => setAttempt((n) => n + 1)}>
        <Text style={styles.buttonText}>נסה שוב</Text>
      </Pressable>
    </View>;
  }
  if (state.kind === 'missing') {
    return <MissingProduct barcode={state.barcode} />;
  }

  return (
    <ProductScreen product={state.product} onReportInaccuracy={openReport} />
  );
}

function MissingProduct({ barcode }: { barcode: string }): React.ReactElement {
  return (
    <View style={styles.screen}>
      <View style={styles.missing}>
        <Text style={styles.missingTitle}>לא מצאנו את המוצר</Text>
        <Text style={styles.missingBarcode}>{barcode}</Text>
        <Text style={styles.missingBody}>
          הברקוד הזה אינו במאגר שלנו ולא נמצא במאגרים הפתוחים. זה קורה בעיקר
          במוצרי יבוא פרטי ובמותגים פרטיים של רשתות.
        </Text>
        <Text style={styles.missingBody}>
          אפשר לפתוח דיווח ולהוסיף פרטים או תמונת תווית בטופס. הדיווח לא משנה את נתוני המוצר אוטומטית.
        </Text>
        <Pressable accessibilityRole="button" style={styles.button} onPress={() => openReport(barcode)}>
          <Text style={styles.buttonText}>פתח דיווח על מוצר חסר</Text>
        </Pressable>
      </View>
      <WarningBar />
    </View>
  );
}

function openReport(barcode: string): void {
  // Opens a draft only. The user reviews and submits it in GitHub.
  const title = encodeURIComponent(`דיווח על מוצר ${barcode}`);
  const body = encodeURIComponent(`ברקוד: ${barcode}\n\nמה חסר או שגוי?\n\nאפשר לצרף צילום תווית לאחר פתיחת הטופס. אין לצרף פרטים רפואיים אישיים.`);
  Linking.openURL(`https://github.com/2130tomer/allergen/issues/new?title=${title}&body=${body}`)
    .catch(() => Alert.alert('הדיווח לא נפתח', 'נסה שוב לאחר בדיקת החיבור.'));
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: color.ground },
  centered: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: color.ground,
  },
  missing: { flex: 1, padding: space.xl, gap: space.md },
  missingTitle: {
    ...typeScale.screenTitle,
    color: color.ink,
    textAlign: 'right',
    writingDirection: 'rtl',
  },
  missingBarcode: { ...typeScale.barcode, color: color.inkFaint, textAlign: 'right' },
  missingBody: {
    ...typeScale.body,
    color: color.inkMuted,
    textAlign: 'right',
    writingDirection: 'rtl',
  },
  button: {
    minHeight: TOUCH_TARGET,
    marginTop: space.md,
    borderRadius: radius.control,
    backgroundColor: color.action,
    alignItems: 'center',
    justifyContent: 'center',
  },
  buttonText: { ...typeScale.bodyStrong, color: color.onAction },
});
