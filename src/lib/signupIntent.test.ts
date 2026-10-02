import { beforeEach, describe, expect, test } from 'vitest';
import { clearIntent, handoffHref, loadIntent, parseIntent, saveIntent } from './signupIntent';

beforeEach(() => sessionStorage.clear());

describe('parseIntent', () => {
  test('accepts known app and plan', () => {
    expect(parseIntent('?app=naforo&plan=premium')).toEqual({ app: 'naforo', plan: 'premium' });
    expect(parseIntent('?app=yiriba')).toEqual({ app: 'yiriba', plan: 'free' });
    expect(parseIntent('?app=kelen&plan=free')).toEqual({ app: 'kelen', plan: 'free' });
  });
  test('is case-insensitive', () => {
    expect(parseIntent('?app=NAFORO&plan=Premium')).toEqual({ app: 'naforo', plan: 'premium' });
  });
  test('ignores unknown or hostile values', () => {
    expect(parseIntent('')).toBeNull();
    expect(parseIntent('?plan=premium')).toBeNull();
    expect(parseIntent('?app=pazuru')).toBeNull();
    expect(parseIntent('?app=https://evil.example')).toBeNull();
    expect(parseIntent('?app=naforo&plan=enterprise')).toEqual({ app: 'naforo', plan: 'free' });
    expect(parseIntent('?app=naforo&plan=<script>')).toEqual({ app: 'naforo', plan: 'free' });
  });
});

describe('storage', () => {
  test('round-trips and clears', () => {
    saveIntent({ app: 'yiriba', plan: 'premium' });
    expect(loadIntent()).toEqual({ app: 'yiriba', plan: 'premium' });
    clearIntent();
    expect(loadIntent()).toBeNull();
  });
  test('rejects tampered storage', () => {
    sessionStorage.setItem('foroba.signupIntent', '{"app":"evil","plan":"x"}');
    expect(loadIntent()).toBeNull();
    sessionStorage.setItem('foroba.signupIntent', 'not json');
    expect(loadIntent()).toBeNull();
  });
});

describe('handoffHref', () => {
  test('maps app to the existing same-origin handoff endpoint', () => {
    expect(handoffHref('naforo')).toBe('/foroba-api/auth/handoff/pazuru?redirect=/settings');
    expect(handoffHref('yiriba')).toBe('/foroba-api/auth/handoff/tsumi?redirect=/settings');
    expect(handoffHref('kelen')).toBeNull();
  });
});
