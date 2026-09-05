/**
 * שורש האפליקציה: RTL, גופנים, שער התנאים, וניווט.
 *
 * שער התנאים עוטף הכל ולא יושב כמסך בתוך הניווט, כדי שלא תהיה שום
 * דרך להגיע למידע על מוצר בלי לעבור דרכו. הוא חוזר גם כשחוזרים מהרקע
 * אחרי יותר מ-30 דקות.
 */

import {
  Assistant_400Regular,
  Assistant_600SemiBold,
  Assistant_700Bold,
} from '@expo-google-fonts/assistant';
import { RobotoMono_400Regular } from '@expo-google-fonts/roboto-mono';
import { SuezOne_400Regular } from '@expo-google-fonts/suez-one';
import { NavigationContainer, useNavigation } from '@react-navigation/native';
import {
  createNativeStackNavigator,
  type NativeStackNavigationProp,
} from '@react-navigation/native-stack';
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import MaterialCommunityIcons from '@expo/vector-icons/MaterialCommunityIcons';
import { useFonts } from 'expo-font';
import * as SplashScreen from 'expo-splash-screen';
import { StatusBar } from 'expo-status-bar';
import React, { useCallback, useEffect, useRef, useState } from 'react';
import {
  ActivityIndicator,
  AppState,
  I18nManager,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import { SafeAreaProvider } from 'react-native-safe-area-context';

import { installBundledSnapshot, type BootstrapOutcome } from './src/db/bootstrap';
import { ProductScreenContainer } from './src/screens/ProductScreenContainer';
import { BrowseScreen } from './src/screens/BrowseScreen';
import { FilterScreen } from './src/screens/FilterScreen';
import { ScannerScreen } from './src/screens/ScannerScreen';
import { TermsScreen } from './src/screens/TermsScreen';
import { FilterProvider } from './src/state/FilterContext';
import { needsAcceptance, readTermsState, recordAcceptance } from './src/state/terms';
import { color, font, typeScale } from './src/theme';

// עברית היא שפת הממשק היחידה, והכיוון נישא כולו בעיצוב: textAlign
// ו-writingDirection על כל סולם הטיפוגרפיה, ו-row-reverse מפורש בכל
// שורה שסדר האיברים בה משמעותי. ראו theme.ts.
//
// לכן RTL של המנוע מכובה במפורש, וזה נראה הפוך מהכוונה עד שמבינים
// למה. row-reverse אינו מוחלט אלא יחסי לכיוון המנוע: כשהמנוע ב-RTL
// הוא ממראה את השורה בעצמו, ו-row-reverse ממראה אותה בחזרה לשמאל-
// לימין. כלומר הפעלת forceRTL יחד עם row-reverse מבטלת את עצמה.
//
// זה גם הסביר תקלה שנראתה אקראית: forceRTL באנדרואיד תופס רק אחרי
// הפעלה מחדש של התהליך, ולכן הריצה הראשונה אחרי התקנה נראתה תקינה
// והריצות שאחריה התהפכו. עם המנוע מכובה הפריסה זהה בכל ריצה.
I18nManager.allowRTL(false);
I18nManager.forceRTL(false);

SplashScreen.preventAutoHideAsync().catch(() => undefined);

export type RootStackParamList = {
  Tabs: undefined;
  Product: { barcode: string };
};

const Stack = createNativeStackNavigator<RootStackParamList>();
const Tabs = createBottomTabNavigator();

/**
 * מסך המוצר יושב ב-stack ההורה ולא בלשוניות, ולכן הניווט אליו מוקלד
 * מול RootStackParamList ולא מול טיפוס הלשוניות.
 */
type RootNavigation = NativeStackNavigationProp<RootStackParamList>;

function BrowseTab(): React.ReactElement {
  const navigation = useNavigation<RootNavigation>();
  return (
    <BrowseScreen
      onSelectProduct={(barcode) => navigation.navigate('Product', { barcode })}
    />
  );
}

function ScanTab(): React.ReactElement {
  const navigation = useNavigation<RootNavigation>();
  const open = (barcode: string) => navigation.navigate('Product', { barcode });
  // גם ברקוד שלא נמצא נפתח באותו מסך, שמטפל בעצמו במצב "לא מצאנו".
  return <ScannerScreen onFound={open} onNotFound={open} />;
}

/** אייקון לשונית. בלי אייקון מפורש הניווט מצייר צורת ברירת מחדל שדורסת את הכיתוב. */
function tabIcon(name: React.ComponentProps<typeof MaterialCommunityIcons>['name']) {
  return ({ color: tint, size }: { color: string; size: number }) => (
    <MaterialCommunityIcons name={name} size={size} color={tint} />
  );
}

function TabsNavigator(): React.ReactElement {
  return (
    <Tabs.Navigator
      screenOptions={{
        headerShown: false,
        tabBarActiveTintColor: color.action,
        tabBarInactiveTintColor: color.inkMuted,
        tabBarLabelStyle: { fontFamily: font.bodyMedium, fontSize: 12 },
        tabBarStyle: {
          backgroundColor: color.surface,
          borderTopColor: color.rule,
          height: 62,
          paddingBottom: 6,
          paddingTop: 6,
        },
      }}
    >
      <Tabs.Screen
        name="Browse"
        options={{ title: 'מוצרים', tabBarIcon: tabIcon('format-list-bulleted') }}
        component={BrowseTab}
      />
      <Tabs.Screen
        name="Scan"
        options={{ title: 'סריקה', tabBarIcon: tabIcon('barcode-scan') }}
        component={ScanTab}
      />
      <Tabs.Screen
        name="Filter"
        options={{ title: 'סינון', tabBarIcon: tabIcon('filter-variant') }}
        component={FilterScreen}
      />
    </Tabs.Navigator>
  );
}

export default function App(): React.ReactElement | null {
  const [fontsLoaded] = useFonts({
    Assistant_400Regular,
    Assistant_600SemiBold,
    Assistant_700Bold,
    SuezOne_400Regular,
    RobotoMono_400Regular,
  });
  const [gateOpen, setGateOpen] = useState(false);
  const [gateChecked, setGateChecked] = useState(false);
  const [database, setDatabase] = useState<BootstrapOutcome | null>(null);
  const backgroundedAt = useRef<number | null>(null);

  useEffect(() => {
    installBundledSnapshot().then(setDatabase);
  }, []);

  const evaluateGate = useCallback(async () => {
    const state = await readTermsState();
    setGateOpen(!needsAcceptance(state));
    setGateChecked(true);
  }, []);

  useEffect(() => {
    evaluateGate();
  }, [evaluateGate]);

  useEffect(() => {
    const subscription = AppState.addEventListener('change', (next) => {
      if (next === 'background' || next === 'inactive') {
        backgroundedAt.current = Date.now();
      } else if (next === 'active' && backgroundedAt.current !== null) {
        evaluateGate();
      }
    });
    return () => subscription.remove();
  }, [evaluateGate]);

  useEffect(() => {
    if (fontsLoaded && gateChecked && database) {
      SplashScreen.hideAsync().catch(() => undefined);
    }
  }, [fontsLoaded, gateChecked, database]);

  if (!fontsLoaded || !gateChecked || !database) {
    return (
      <View style={styles.loading}>
        <ActivityIndicator color={color.action} />
      </View>
    );
  }

  // בלי מאגר אין לאפליקציה מה להגיד, ועדיף לומר זאת מפורשות מאשר להציג
  // מסכים ריקים שנראים כמו קטלוג בלי מוצרים.
  if (database.kind === 'failed') {
    return (
      <SafeAreaProvider style={styles.root}>
        <View style={styles.loading}>
          <Text style={styles.errorTitle}>המאגר לא נטען</Text>
          <Text style={styles.errorBody}>{database.reason}</Text>
        </View>
      </SafeAreaProvider>
    );
  }

  const accept = async () => {
    await recordAcceptance();
    setGateOpen(true);
  };

  return (
    <SafeAreaProvider style={styles.root}>
      <StatusBar style="dark" />
      {gateOpen ? (
        <FilterProvider>
          <NavigationContainer>
            <Stack.Navigator
              screenOptions={{
                headerTitleStyle: { ...typeScale.bodyStrong, color: color.ink },
                headerStyle: { backgroundColor: color.surface },
                headerTintColor: color.action,
                contentStyle: { backgroundColor: color.ground },
              }}
            >
              <Stack.Screen
                name="Tabs"
                component={TabsNavigator}
                options={{ headerShown: false }}
              />
              <Stack.Screen
                name="Product"
                component={ProductScreenContainer}
                options={{ title: 'פרטי מוצר' }}
              />
            </Stack.Navigator>
          </NavigationContainer>
        </FilterProvider>
      ) : (
        <TermsScreen onAccept={accept} />
      )}
    </SafeAreaProvider>
  );
}

const styles = StyleSheet.create({
  root: {
    flex: 1,
  },
  errorTitle: {
    ...typeScale.screenTitle,
    color: color.ink,
    textAlign: 'center',
    paddingHorizontal: 24,
  },
  errorBody: {
    ...typeScale.body,
    color: color.inkMuted,
    textAlign: 'center',
    paddingHorizontal: 24,
    paddingTop: 8,
  },
  loading: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: color.ground,
  },
});
