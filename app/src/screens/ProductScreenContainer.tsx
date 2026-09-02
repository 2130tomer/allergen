/**
 * טעינת מוצר למסך המוצר, כולל שני מצבי הכישלון.
 *
 * מוצר שאינו במאגר המקומי אינו סוף הדרך: מנסים פנייה חיה ל-Open Food
 * Facts, ורק אם גם היא נכשלת מוצג מסך לא מצאנו עם הצעה לצלם תווית.
 * הצילום נכנס לתור עיבוד ואינו הופך לתשובה מיידית.
 */

import type { NativeStackScreenProps } from '@react-navigation/native-stack';
import React, { useEffect, useState } from 'react';
import { ActivityIndicator, Pressable, StyleSheet, Text, View } from 'react-native';

import type { RootStackParamList } from '../../App';
import { WarningBar } from '../components/WarningBar';
import { loadProduct, type ProductDetail } from '../db/queries';
import { fetchFromOpenFoodFacts } from '../net/openFoodFacts';
import { ProductScreen } from './ProductScreen';
import { color, radius, space, TOUCH_TARGET, typeScale } from '../theme';

type Props = NativeStackScreenProps<RootStackParamList, 'Product'>;

type State =
  | { kind: 'loading' }
  | { kind: 'ready'; product: ProductDetail }
  | { kind: 'missing'; barcode: string };

export function ProductScreenContainer({ route }: Props): React.ReactElement {
  const { barcode } = route.params;
  const [state, setState] = useState<State>({ kind: 'loading' });

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
    })().catch(() => {
      if (!cancelled) setState({ kind: 'missing', barcode });
    });

    return () => {
      cancelled = true;
    };
  }, [barcode]);

  if (state.kind === 'loading') {
    return (
      <View style={styles.centered}>
        <ActivityIndicator color={color.action} />
      </View>
    );
  }

  if (state.kind === 'missing') {
    return <MissingProduct barcode={state.barcode} />;
  }

  return (
    <ProductScreen product={state.product} onReportInaccuracy={() => undefined} />
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
          אפשר לצלם את התווית ולעזור לנו להוסיף אותו. הצילום נכנס לעיבוד ולא
          יוצג כתשובה מיידית, כי מידע שלא אומת אינו יכול לקבוע שאלרגן נעדר.
        </Text>
        <Pressable accessibilityRole="button" style={styles.button}>
          <Text style={styles.buttonText}>צלם את התווית</Text>
        </Pressable>
      </View>
      <WarningBar />
    </View>
  );
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
