import { describe, it, expect } from 'vitest';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

const root = resolve(__dirname, '../..');
const read = (p: string) => readFileSync(resolve(root, p), 'utf8');

describe('Kelen branding', () => {
  const html = read('index.html');

  it('marks the document as the kelen app', () => {
    expect(html).toMatch(/<html[^>]*data-app="kelen"/);
  });

  it('uses the Kelen title, icons and no Foroba-teal leftovers', () => {
    expect(html).toMatch(/<title>Kelen by Foroba<\/title>/);
    expect(html).toContain('apple-mobile-web-app-title" content="Kelen"');
    expect(html).toContain('/icons/kelen-180.png');
    expect(html).not.toMatch(/#0D9488/i);
  });

  it('loads Geist fonts from fontsource and uses Geist as the body font', () => {
    const main = read('src/main.tsx');
    expect(main).toContain('@fontsource-variable/geist');
    expect(main).toContain('@fontsource-variable/geist-mono');
    expect(read('src/global.css')).toMatch(/font-family:\s*"Geist Variable"/);
  });

  it('names the PWA manifest Kelen with the Kelen accent', () => {
    const manifest = JSON.parse(read('public/manifest.json'));
    expect(manifest.name).toBe('Kelen by Foroba');
    expect(manifest.short_name).toBe('Kelen');
    expect(manifest.theme_color).toBe('#2F5BEA');
    const vite = read('vite.config.ts');
    expect(vite).toContain("name: 'Kelen by Foroba'");
    expect(vite).toContain('/icons/kelen-512.png');
  });
});
