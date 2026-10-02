import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';

// jsdom has no layout, so the real measurements run in Playwright (BR-5 T6 / BR-7 audit).
// This guards the rule itself against being deleted.
describe('mobile form-control CSS', () => {
  const css = readFileSync(join(__dirname, 'global.css'), 'utf8');
  const block =
    css.match(/@media \(max-width: 767px\)(, \(pointer: coarse\))?\s*{[^]*?}\s*}/g)?.find((b) => b.includes('input')) ?? '';

  it('keeps inputs at 16px / 44px on phones and touch tablets', () => {
    expect(block).toContain('(pointer: coarse)');
    expect(block).toContain('font-size: 16px');
    expect(block).toContain('min-height: 44px');
    expect(block).toMatch(/input:not\(\[type='checkbox'\]\)/);
  });
});
