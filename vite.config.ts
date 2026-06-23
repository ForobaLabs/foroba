import tailwindcss from '@tailwindcss/vite';
import react from '@vitejs/plugin-react';
import { defineConfig, loadEnv } from 'vite';

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '');
  return {
    plugins: [react(), tailwindcss()],
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
        },
      },
    },
  };
});
