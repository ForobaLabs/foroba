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
    define: {
      __APP_VERSION__: JSON.stringify(process.env.npm_package_version ?? '0.1.0'),
    },
    server: {
      port: 5175,
      proxy: {
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
