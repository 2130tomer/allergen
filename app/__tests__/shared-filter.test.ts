import cases from '../../shared/filter-cases.json';
import { applyFilter, type AllergenLevels, policyOf, withPolicy, EMPTY_SELECTION } from '../src/domain/filter';
for (const item of cases) {
  test(item.name, () => {
    expect(applyFilter({ contains: new Set(item.contains), mayContain: new Set(item.may) },
      item.levels as AllergenLevels).visibility).toBe(item.visibility);
  });
}
test('policy changes remove obsolete exclusions', () => {
  const strict = withPolicy(EMPTY_SELECTION, 'soy', 'contains_and_may');
  expect(policyOf(strict, 'soy')).toBe('contains_and_may');
  const contains = withPolicy(strict, 'soy', 'contains');
  expect(contains.mayContain.has('soy')).toBe(false);
  expect(policyOf(withPolicy(contains, 'soy', 'none'), 'soy')).toBe('none');
});
