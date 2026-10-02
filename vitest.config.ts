import { defineConfig } from 'vitest/config';

export default defineConfig({
  resolve: {
    // @foroba/ui (file: dep) resolves its own copy of these singleton-context libraries;
    // without dedupe its hooks read a QueryClient context the test never populated.
    dedupe: ['@tanstack/react-query', 'react', 'react-dom'],
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/test/setup.ts'],
    // Process @foroba/ui through Vite so the dedupe above applies to its imports.
    server: { deps: { inline: [/@foroba\/ui/] } },
  },
});
