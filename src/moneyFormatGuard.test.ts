import { readdirSync, readFileSync, statSync } from 'node:fs';
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';

function walk(dir: string): string[] {
  return readdirSync(dir).flatMap((n) => {
    const p = join(dir, n);
    return statSync(p).isDirectory() ? walk(p) : /\.(ts|tsx)$/.test(n) && !/\.test\./.test(n) ? [p] : [];
  });
}

describe('money formatting guard (ID-18)', () => {
  const files = walk(__dirname);

  it('formats currency only through @foroba/ui formatCurrency', () => {
    const offenders = files.filter((f) => /style:\s*['"]currency['"]/.test(readFileSync(f, 'utf8')));
    expect(offenders).toEqual([]);
  });

  it('never builds a money string from a symbol plus toFixed', () => {
    const offenders = files.filter((f) => /[€$£]\$\{[^}]*toFixed\(/.test(readFileSync(f, 'utf8')));
    expect(offenders).toEqual([]);
  });
});
