import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';

// jsdom has no layout; the 375px FR overflow was measured in Playwright (BR-8 round 3).
// This guards the wrapping classes that fixed it.
describe('AccountsPage header wraps on narrow screens', () => {
  const src = readFileSync(join(__dirname, 'AccountsPage.tsx'), 'utf8');
  it('lets the title row and the action group wrap', () => {
    expect(src).toMatch(/flex flex-wrap items-start justify-between gap-3 mb-6/);
    expect(src).toMatch(/flex flex-wrap items-center gap-2">\s*<ConnectBankButton/);
  });
});
