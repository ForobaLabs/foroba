import tailwindcss from '@tailwindcss/vite';
import react from '@vitejs/plugin-react';
import { defineConfig, loadEnv } from 'vite';
import { VitePWA } from 'vite-plugin-pwa';

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '');
  return {
    plugins: [
      react(),
      tailwindcss(),
      VitePWA({
        registerType: 'autoUpdate',
        includeAssets: ['favicon.svg', 'icons/*.svg'],
        manifest: {
          name: 'Foroba — Personal Finance Hub',
          short_name: 'Foroba',
          description: 'Local-first personal finance superapp',
          theme_color: '#0D9488',
          background_color: '#0F1117',
          display: 'standalone',
          orientation: 'portrait',
          start_url: '/',
          scope: '/',
          icons: [
            { src: '/icons/icon-192x192.svg', sizes: '192x192', type: 'image/svg+xml' },
            { src: '/icons/icon-512x512.svg', sizes: '512x512', type: 'image/svg+xml' },
            { src: '/icons/icon-512x512.svg', sizes: '512x512', type: 'image/svg+xml', purpose: 'any maskable' },
          ],
        },
        workbox: {
          globPatterns: ['**/*.{js,css,html,ico,svg,woff2}'],
          runtimeCaching: [
            {
              urlPattern: /^\/auth\//,
              handler: 'NetworkFirst',
              options: { cacheName: 'auth-cache', networkTimeoutSeconds: 10 },
            },
            {
              urlPattern: /^\/jeli\//,
              handler: 'NetworkOnly',
            },
          ],
        },
      }),
    ],
    optimizeDeps: {
      exclude: ['@foroba/ui', '@foroba/ui/i18n', '@foroba/ui/charts'],
    },
    resolve: {
      // @foroba/ui is consumed via a `file:` dependency and resolves its own
      // node_modules copy of these singleton-context libraries separately from
      // this app's copy (divergent versions: @tanstack/react-query ^5.101.0 here
      // vs ^5.101.1 in foroba-ui). Without dedupe, two physical module instances
      // get bundled, so foroba-ui's useEntitlement()/LockedFeature() reads a
      // QueryClient context this app's <QueryClientProvider> never populated,
      // throwing "No QueryClient set" at runtime (same root cause as tsumi#183).
      dedupe: ['@tanstack/react-query', 'react', 'react-dom'],
    },
    define: {
      __APP_VERSION__: JSON.stringify(process.env.npm_package_version ?? '0.1.0'),
    },
    server: {
      port: 5175,
      proxy: {
        '/api/v1/foroba': {
          target: 'http://localhost:8002',
          changeOrigin: true,
          rewrite: (p) => p.replace(/^\/api\/v1\/foroba/, ''),
        },
        '/api/v1/pazuru': {
          target: 'http://localhost:8000',
          changeOrigin: true,
          rewrite: (p) => p.replace(/^\/api\/v1\/pazuru/, ''),
        },
        '/api/v1/tsumi': {
          target: 'http://localhost:8050',
          changeOrigin: true,
          rewrite: (p) => p.replace(/^\/api\/v1\/tsumi/, ''),
        },
        '/pazuru-api': {
          target: env.VITE_PAZURU_API_URL ?? 'http://localhost:8000',
          changeOrigin: true,
          rewrite: (p) => p.replace('/pazuru-api', ''),
        },
        '/tsumi-api': {
          target: env.VITE_TSUMI_API_URL ?? 'http://localhost:8050',
          changeOrigin: true,
          rewrite: (p) => p.replace('/tsumi-api', ''),
        },
        '/jeli': {
          target: env.VITE_JELI_API_URL ?? 'http://localhost:8002',
          changeOrigin: true,
          rewrite: (p) => p.replace(/^\/jeli/, ''),
        },
        '/foroba-api': {
          target: env.VITE_FOROBA_API_URL ?? 'http://localhost:8002',
          changeOrigin: true,
          rewrite: (p) => p.replace('/foroba-api', ''),
        },
      },
    },
  };
});
