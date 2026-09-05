/** One explicit exclusion policy per allergen. */
import React from 'react';
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { ALLERGEN_LIST, expandSelection } from '../domain/allergens';
import { policyOf, type FilterPolicy } from '../domain/filter';
import { useFilter } from '../state/FilterContext';
import { color, space, TOUCH_TARGET, typeScale } from '../theme';

const POLICIES: { id: FilterPolicy; label: string }[] = [
  { id: 'none', label: 'ללא סינון' },
  { id: 'contains', label: 'הסתר מכיל' },
  { id: 'contains_and_may', label: 'הסתר מכיל ועלול להכיל' },
];
export function FilterScreen(): React.ReactElement {
  const { selection, setPolicy, clear, isLoaded } = useFilter();
  return (
    <SafeAreaView style={styles.screen}>
      <ScrollView contentContainerStyle={styles.content}>
        <Text style={styles.title}>מה להסתיר</Text>
        <Text style={styles.note}>בחירה בקבוצה כוללת את תת־הסוגים שלה. אין מידע אינו היעדר אלרגן.</Text>
        <Pressable accessibilityRole="button" onPress={clear} disabled={!isLoaded} style={styles.option}>
          <Text style={styles.label}>נקה הכל</Text>
        </Pressable>
        {ALLERGEN_LIST.map((allergen) => {
          const policy = policyOf(selection, allergen.id);
          const groups = ALLERGEN_LIST.filter((group) => group.id !== allergen.id &&
            policyOf(selection, group.id) !== 'none' && expandSelection([group.id]).has(allergen.id));
          return (
            <View key={allergen.id} style={styles.row}>
              <Text style={styles.label}>{allergen.labelHe}</Text>
              {groups.length > 0 ? <Text style={styles.note}>
                בנוסף חלה בחירת הקבוצה: {groups.map((group) => group.labelHe).join(', ')}
              </Text> : null}
              {allergen.noteHe ? <Text style={styles.note}>{allergen.noteHe}</Text> : null}
              <View accessibilityRole="radiogroup">
                {POLICIES.map((item) => (
                  <Pressable key={item.id} accessibilityRole="radio"
                    accessibilityLabel={`${allergen.labelHe}: ${item.label}`}
                    accessibilityState={{ checked: policy === item.id }} disabled={!isLoaded}
                    onPress={() => setPolicy(allergen.id, item.id)}
                    style={[styles.option, policy === item.id && styles.selected]}>
                    <Text style={styles.label}>{item.label}</Text>
                  </Pressable>
                ))}
              </View>
            </View>
          );
        })}
      </ScrollView>
    </SafeAreaView>
  );
}
const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: color.ground },
  content: { padding: space.lg, gap: space.md },
  title: { ...typeScale.screenTitle, color: color.ink, textAlign: 'right' },
  label: { ...typeScale.body, color: color.ink, textAlign: 'right' },
  note: { ...typeScale.caption, color: color.inkMuted, textAlign: 'right' },
  row: { backgroundColor: color.surface, padding: space.md, gap: space.sm },
  option: { minHeight: TOUCH_TARGET, justifyContent: 'center', padding: space.sm, borderWidth: 1, borderColor: color.rule },
  selected: { backgroundColor: color.cautionSoft, borderColor: color.action },
});
