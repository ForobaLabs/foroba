import { describe, it, expect } from 'vitest';
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join, resolve } from 'node:path';

const root = resolve(__dirname, '../..');

function walk(dir: string, out: string[] = []): string[] {
  for (const name of readdirSync(dir)) {
    const p = join(dir, name);
    if (statSync(p).isDirectory()) walk(p, out);
    else out.push(p);
  }
  return out;
}

/** Drops comments so only strings, JSX text and identifiers remain. */
const stripComments = (text: string) =>
  text.replace(/\/\*[\s\S]*?\*\//g, '').replace(/(^|[^:'"`\\])\/\/.*$/gm, '$1');

const sources = walk(join(root, 'src')).filter(
  (f) => /\.(tsx?|css)$/.test(f) && !/\.test\.tsx?$/.test(f) && !f.includes('/test/'),
);
const visible = [...sources, join(root, 'index.html'), join(root, 'public/manifest.json')];

const offenders = (re: RegExp) =>
  visible
    .filter((f) => re.test(stripComments(readFileSync(f, 'utf8'))))
    .map((f) => f.replace(`${root}/`, ''));

// Standalone words only: identifiers (PazuruHealth, usePazuruHealth) and lowercase
// keys/paths ('pazuru', /pazuru-api, stepup_pazuru) are internal and stay.
describe('forbidden user-visible strings', () => {
  it('never shows the old product name Pazuru', () => {
    expect(offenders(/\bPazuru\b/)).toEqual([]);
  });
  it('never shows the old product name Tsumi', () => {
    expect(offenders(/\bTsumi\b/)).toEqual([]);
  });
  it('never shows Foroba 360 / 360° as a product label', () => {
    expect(offenders(/Foroba 360|360°/)).toEqual([]);
  });
});
