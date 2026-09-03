/**
 * עיון וחיפוש באותו מסך.
 *
 * שדה אחד עונה על שלושת המקרים שביקשנו: שם מוצר, שם מחלקה, וברקוד
 * מוקלד. כשהשדה ריק מוצג עץ המחלקות; ברגע שמקלידים הוא מתחלף בתוצאות.
 * אין מסך חיפוש נפרד, כי מסך נוסף הוא עוד לחיצה בעמידה מול מדף.
 */

import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  ActivityIndicator,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { ProductList } from '../components/ProductList';
import {
  levelsFor,
  listByDepartment,
  listDepartments,
  search,
  type Department,
  type ProductSummary,
} from '../db/queries';
import type { AllergenLevels } from '../domain/filter';
import { looksLikeBarcode } from '../text/hebrew';
import { useFilter } from '../state/FilterContext';
import { color, radius, space, TOUCH_TARGET, typeScale } from '../theme';

interface Props {
  onSelectProduct: (barcode: string) => void;
}

export function BrowseScreen({ onSelectProduct }: Props): React.ReactElement {
  const { selection } = useFilter();
  const [query, setQuery] = useState('');
  const [departments, setDepartments] = useState<Department[]>([]);
  const [openDepartment, setOpenDepartment] = useState<string | null>(null);
  const [products, setProducts] = useState<ProductSummary[]>([]);
  const [levels, setLevels] = useState<Record<string, AllergenLevels>>({});
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    listDepartments().then(setDepartments).catch(() => setDepartments([]));
  }, []);

  const loadLevels = useCallback(async (found: ProductSummary[]) => {
    const byBarcode = await levelsFor(found.map((product) => product.barcode));
    setLevels(byBarcode);
  }, []);

  useEffect(() => {
    const trimmed = query.trim();
    if (trimmed.length === 0) {
      setProducts([]);
      return;
    }

    let cancelled = false;
    setIsLoading(true);
    // ברקוד מלא הוא שאילתה מדויקת ואין טעם להשהות אותה.
    const delay = looksLikeBarcode(trimmed) ? 0 : 220;
    const timer = setTimeout(() => {
      search(trimmed)
        .then(async (results) => {
          if (cancelled) return;
          setProducts(results.products);
          await loadLevels(results.products);
        })
        .catch(() => {
          if (!cancelled) setProducts([]);
        })
        .finally(() => {
          if (!cancelled) setIsLoading(false);
        });
    }, delay);

    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [query, loadLevels]);

  const openSubDepartment = useCallback(
    async (departmentId: string) => {
      setIsLoading(true);
      setOpenDepartment(departmentId);
      try {
        const found = await listByDepartment(departmentId);
        setProducts(found);
        await loadLevels(found);
      } finally {
        setIsLoading(false);
      }
    },
    [loadLevels],
  );

  const topLevel = useMemo(
    () => departments.filter((department) => department.parentId === null),
    [departments],
  );

  const isSearching = query.trim().length > 0;
  const showList = isSearching || openDepartment !== null;

  return (
    <SafeAreaView style={styles.screen} edges={['top']}>
      <View style={styles.searchBar}>
        <TextInput
          value={query}
          onChangeText={setQuery}
          placeholder="חיפוש מוצר, מחלקה או ברקוד"
          placeholderTextColor={color.inkFaint}
          style={styles.input}
          returnKeyType="search"
          clearButtonMode="while-editing"
          accessibilityLabel="שדה חיפוש"
        />
        {showList ? (
          <Pressable
            accessibilityRole="button"
            onPress={() => {
              setQuery('');
              setOpenDepartment(null);
              setProducts([]);
            }}
            style={styles.backButton}
          >
            <Text style={styles.backText}>למחלקות</Text>
          </Pressable>
        ) : null}
      </View>

      {isLoading ? (
        <ActivityIndicator style={styles.loader} color={color.action} />
      ) : null}

      {showList ? (
        <ProductList
          products={products}
          levelsByBarcode={levels}
          selection={selection}
          onSelect={onSelectProduct}
          emptyMessage={
            looksLikeBarcode(query)
              ? 'הברקוד הזה אינו במאגר המקומי.'
              : 'לא נמצאו מוצרים מתאימים.'
          }
        />
      ) : (
        <ScrollView contentContainerStyle={styles.departments}>
          {topLevel.map((department) => {
            const children = departments.filter(
              (candidate) => candidate.parentId === department.id,
            );
            // מחלקה בלי תת-מחלקות, כמו פירות וירקות, נפתחת ישירות מהכותרת
            // שלה. בלי זה היא מוצגת ככותרת ריקה שאי אפשר ללחוץ עליה.
            const openable = children.length > 0 ? children : [department];
            return (
              <View key={department.id} style={styles.departmentGroup}>
                <Text style={styles.departmentTitle}>{department.labelHe}</Text>
                <View style={styles.chips}>
                  {openable.map((child) => (
                    <Pressable
                      key={child.id}
                      accessibilityRole="button"
                      onPress={() => openSubDepartment(child.id)}
                      style={({ pressed }) => [styles.chip, pressed && styles.chipPressed]}
                    >
                      <Text style={styles.chipText}>
                        {child.id === department.id ? 'הצג הכל' : child.labelHe}
                      </Text>
                    </Pressable>
                  ))}
                </View>
              </View>
            );
          })}
        </ScrollView>
      )}
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: color.ground },
  searchBar: {
    flexDirection: 'row-reverse',
    alignItems: 'center',
    gap: space.sm,
    paddingHorizontal: space.lg,
    paddingVertical: space.md,
    backgroundColor: color.surface,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: color.rule,
  },
  input: {
    ...typeScale.body,
    flex: 1,
    minHeight: TOUCH_TARGET,
    paddingHorizontal: space.md,
    borderRadius: radius.control,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: color.rule,
    backgroundColor: color.ground,
    color: color.ink,
    textAlign: 'right',
    writingDirection: 'rtl',
  },
  backButton: { paddingHorizontal: space.sm, paddingVertical: space.sm },
  backText: { ...typeScale.label, color: color.action },
  loader: { marginTop: space.lg },
  departments: { padding: space.lg, gap: space.xl },
  departmentGroup: { gap: space.sm },
  departmentTitle: {
    ...typeScale.screenTitle,
    fontSize: 20,
    color: color.ink,
    textAlign: 'right',
    writingDirection: 'rtl',
  },
  chips: { flexDirection: 'row-reverse', flexWrap: 'wrap', gap: space.sm },
  chip: {
    minHeight: 40,
    justifyContent: 'center',
    paddingHorizontal: space.lg,
    borderRadius: radius.pill,
    backgroundColor: color.surface,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: color.rule,
  },
  chipPressed: { backgroundColor: color.actionSoft, borderColor: color.action },
  chipText: {
    ...typeScale.label,
    color: color.ink,
    writingDirection: 'rtl',
  },
});
