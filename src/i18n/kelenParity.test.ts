import { expect, test } from 'vitest';
import en from './kelen-en.json';
import fr from './kelen-fr.json';
import it from './kelen-it.json';

const flat = (o: object, p = ''): string[] =>
  Object.entries(o).flatMap(([k, v]) => (typeof v === 'object' && v ? flat(v, `${p}${k}.`) : [`${p}${k}`]));

test('onboarding keys exist in en, it and fr', () => {
  const keys = flat(en.onboarding).sort();
  expect(keys.length).toBeGreaterThan(15);
  expect(flat(it.onboarding).sort()).toEqual(keys);
  expect(flat(fr.onboarding).sort()).toEqual(keys);
});

test('data-page keys exist in en, it and fr', () => {
  const keys = flat(en.data).sort();
  expect(keys.length).toBeGreaterThan(60);
  expect(flat(it.data).sort()).toEqual(keys);
  expect(flat(fr.data).sort()).toEqual(keys);
});
