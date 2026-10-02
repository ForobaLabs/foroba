import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { I18nextProvider } from 'react-i18next';
import { RouterProvider } from 'react-router';
import i18n from './i18n';
import { router } from './router';
import { AuthProvider } from './auth/AuthProvider';
import { CurrencyProvider } from './contexts/CurrencyContext';
import '@fontsource-variable/geist';
import '@fontsource-variable/geist-mono';
import './global.css';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      // 2 retries + react-query's default exponential backoff
      // (attempt => min(1000 * 2**attempt, 30000)) so a transiently-down
      // sub-app gets a real chance to recover before we surface an error.
      retry: 2,
      staleTime: 30_000,
    },
  },
});

const rootEl = document.getElementById('root');
if (!rootEl) throw new Error('Root element not found');

createRoot(rootEl).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <CurrencyProvider>
          <I18nextProvider i18n={i18n}>
            <RouterProvider router={router} />
          </I18nextProvider>
        </CurrencyProvider>
      </AuthProvider>
    </QueryClientProvider>
  </StrictMode>
);
