import { describe, expect, it } from 'vitest';
import { parseDecimal } from '../../lib/parseDecimal';
import { MESSAGES, validateScenario } from './validateScenario';
import en from '../../i18n/kelen-en.json';
import it_ from '../../i18n/kelen-it.json';
import fr from '../../i18n/kelen-fr.json';

describe('parseDecimal', () => {
  it.each([
    ['1.234,5', 'en', 1234.5],
    ['1,234.5', 'it', 1234.5],
    ['1.234,5', 'it', 1234.5],
    ['1 234,5', 'fr', 1234.5],
    ['1,5', 'en', 1.5],
    ['1.5', 'it', 1.5],
    ['1,234', 'en', 1234],
    ['1.234', 'it', 1234],
    ['1.234', 'en', 1.234],
    ['1,234', 'it', 1.234],
    ['1.234.567', 'it', 1234567],
    ['−5', 'en', -5],
    ['-2,5', 'it', -2.5],
    ['250 €', 'it', 250],
    ['7%', 'en', 7],
    ['  42 ', 'en', 42],
  ])('%s (%s) → %s', (raw, lang, expected) => {
    expect(parseDecimal(raw, lang)).toBe(expected);
  });

  it.each(['', '   ', 'abc', '1.2.3,4,5x', '--3', 'Infinity', '1e9x'])('rejects %j', (raw) => {
    expect(parseDecimal(raw, 'en')).toBeNaN();
  });
});

describe('validateScenario', () => {
  const ok = { amount: '250', years: '10', rate: '5' };

  it('accepts a valid scenario and returns numbers', () => {
    const r = validateScenario(ok, 'en');
    expect(r.errors).toEqual({});
    expect(r.values).toEqual({ amount: 250, years: 10, rate: 5 });
  });

  it('rejects amount ≤ 0 with a human message', () => {
    expect(validateScenario({ ...ok, amount: '0' }, 'en').errors.amount).toBe('amountMin');
    expect(validateScenario({ ...ok, amount: '-5' }, 'en').errors.amount).toBe('amountMin');
  });

  it('rejects a non-number amount and an absurd amount', () => {
    expect(validateScenario({ ...ok, amount: 'abc' }, 'en').errors.amount).toBe('amountNaN');
    expect(validateScenario({ ...ok, amount: '1000000000' }, 'en').errors.amount).toBe('amountMax');
    expect(validateScenario({ ...ok, amount: '1000000,01' }, 'it').errors.amount).toBe('amountMax');
  });

  it('accepts exactly 1,000,000 as the amount boundary', () => {
    expect(validateScenario({ ...ok, amount: '1.000.000' }, 'it').errors.amount).toBeUndefined();
  });

  it('limits years to whole numbers 1–60', () => {
    for (const years of ['0', '61', '2,5', '-1', '']) {
      expect(validateScenario({ ...ok, years }, 'en').errors.years).toBe('years');
    }
    expect(validateScenario({ ...ok, years: '60' }, 'en').errors.years).toBeUndefined();
    expect(validateScenario({ ...ok, years: '1' }, 'en').errors.years).toBeUndefined();
  });

  it('limits the return rate to −50…50 % and allows 0', () => {
    for (const rate of ['-50,1', '50.1', 'x']) {
      expect(validateScenario({ ...ok, rate }, 'en').errors.rate).toBe('rate');
    }
    for (const rate of ['-50', '50', '0']) {
      expect(validateScenario({ ...ok, rate }, 'en').errors.rate).toBeUndefined();
    }
  });

  it('reports the first invalid field in form order', () => {
    const r = validateScenario({ amount: '0', years: '99', rate: '99' }, 'en');
    expect(r.firstInvalid).toBe('amount');
    expect(validateScenario({ ...ok, years: '99', rate: '99' }, 'en').firstInvalid).toBe('years');
    expect(validateScenario(ok, 'en').firstInvalid).toBeNull();
  });
});

describe('validation copy', () => {
  it('English master JSON matches MESSAGES and IT/FR define every key', () => {
    expect(en.whatif.errors).toEqual(MESSAGES);
    for (const loc of [it_, fr]) expect(Object.keys(loc.whatif.errors).sort()).toEqual(Object.keys(MESSAGES).sort());
  });
});
