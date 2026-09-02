/**
 * מצב הסינון של האפליקציה.
 *
 * מצב יחיד וגלובלי, לא פרופיל. בגרסה 1 אין פרופילים בכלל, ולכן אין
 * כאן מזהה משתמש, אין שרת, ואין סנכרון. הבחירה נשמרת מקומית רק כדי
 * שלא צריך יהיה לסמן אותה מחדש בכל פתיחה.
 */

import AsyncStorage from '@react-native-async-storage/async-storage';
import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from 'react';

import {
  EMPTY_SELECTION,
  deserialize,
  serialize,
  toggle,
  type FilterSelection,
} from '../domain/filter';

const STORAGE_KEY = 'allergen.filter.v1';

interface FilterContextValue {
  selection: FilterSelection;
  isLoaded: boolean;
  toggleContains: (allergenId: string) => void;
  toggleMayContain: (allergenId: string) => void;
  clear: () => void;
}

const FilterContext = createContext<FilterContextValue | null>(null);

export function FilterProvider({
  children,
}: {
  children: React.ReactNode;
}): React.ReactElement {
  const [selection, setSelection] = useState<FilterSelection>(EMPTY_SELECTION);
  const [isLoaded, setIsLoaded] = useState(false);

  useEffect(() => {
    let cancelled = false;
    AsyncStorage.getItem(STORAGE_KEY)
      .then((raw) => {
        if (cancelled) return;
        setSelection(deserialize(raw ? JSON.parse(raw) : null));
      })
      .catch(() => {
        // בחירה שלא נטענה היא בחירה ריקה, לא שגיאה שמונעת שימוש.
        if (!cancelled) setSelection(EMPTY_SELECTION);
      })
      .finally(() => {
        if (!cancelled) setIsLoaded(true);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const persist = useCallback((next: FilterSelection) => {
    setSelection(next);
    AsyncStorage.setItem(STORAGE_KEY, JSON.stringify(serialize(next))).catch(() => {
      // כישלון שמירה אינו משנה את המצב הנוכחי במסך.
    });
  }, []);

  const value = useMemo<FilterContextValue>(
    () => ({
      selection,
      isLoaded,
      toggleContains: (allergenId) =>
        persist({ ...selection, contains: toggle(selection.contains, allergenId) }),
      toggleMayContain: (allergenId) =>
        persist({ ...selection, mayContain: toggle(selection.mayContain, allergenId) }),
      clear: () => persist(EMPTY_SELECTION),
    }),
    [selection, isLoaded, persist],
  );

  return <FilterContext.Provider value={value}>{children}</FilterContext.Provider>;
}

export function useFilter(): FilterContextValue {
  const value = useContext(FilterContext);
  if (!value) throw new Error('useFilter must be used inside FilterProvider');
  return value;
}
