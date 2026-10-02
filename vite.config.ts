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
        devOptions: { enabled: false },
        includeAssets: ['favicon.svg', 'favicon.ico', 'icons/*.png'],
        manifest: {
          name: 'Kelen by Foroba',
          short_name: 'Kelen',
          description: 'Your whole wealth at a glance: net worth, goals and what-if simulation.',
          theme_color: '#2F5BEA',
          background_color: '#0F1117',
          display: 'standalone',
          orientation: 'portrait',
          start_url: '/',
          scope: '/',
          icons: [
            { src: '/icons/kelen-192.png', sizes: '192x192', type: 'image/png' },
            { src: '/icons/kelen-512.png', sizes: '512x512', type: 'image/png' },
            { src: '/icons/kelen-512.png', sizes: '512x512', type: 'image/png', purpose: 'any maskable' },
          ],
        },
        workbox: {
          globPatterns: ['**/*.{js,css,html,ico,svg,woff2}'],
          // Full-page navigations (<a href> clicks, not fetch/XHR) to these backend
          // proxy paths must reach the network and see the real response (redirects,
          // in particular /foroba-api/auth/handoff/* — see foroba#286): Workbox's
          // default navigateFallback otherwise intercepts every navigation request
          // not explicitly denylisted here and serves the cached SPA shell instead.
          navigateFallbackDenylist: [/^\/(foroba|pazuru|tsumi)-api\//, /^\/jeli\//],
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
      // Pre-bundle @foroba/ui (a linked tsup build whose deps are left external)
      // AND its heavy transitive deps up front. Without this, Vite discovers
      // lucide-react / recharts lazily mid-load and forces a full-page reload.
      // Only list packages resolvable from foroba's own node_modules — transitive
      // deps of @foroba/ui (clsx, @radix-ui/*, etc.) are inlined into @foroba/ui's
      // pre-bundle chunk by rolldown and must NOT be listed here (they would fail
      // to resolve and trigger a redundant second optimizer pass).
      include: [
        '@foroba/ui',
        '@foroba/ui/i18n',
        '@foroba/ui/charts',
        '@foroba/ui/api',
        '@foroba/ui/tokens',
        'react',
        'react-dom',
        'react-dom/client',
        'react/jsx-runtime',
        'react-router',
        '@tanstack/react-query',
        'lucide-react',
        'recharts',
        'i18next',
        'react-i18next',
        '@simplewebauthn/browser',
      ],
      // Don't hold the page response while the crawler does its second pass —
      // serve immediately with current cache, reload once if new deps found.
      holdUntilCrawlEnd: false,
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
      warmup: {
        clientFiles: [
          './src/main.tsx',
          './src/App.tsx',
          './src/router.tsx',
          './src/pages/LoginPage.tsx',
          './src/pages/DashboardPage.tsx',
        ],
      },
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
