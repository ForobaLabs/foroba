import { AiApiProvider, applyCspNonce } from '@foroba/ui';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { I18nextProvider } from 'react-i18next';
import { RouterProvider } from 'react-router';
import i18n from './i18n';
import { router } from './router';
import { aiApi } from './ai/aiApi';
import { AuthProvider } from './auth/AuthProvider';
import { CurrencyProvider } from './contexts/CurrencyContext';
import { PrivacyProvider } from './contexts/PrivacyContext';
import '@fontsource-variable/geist';
import '@fontsource-variable/geist-mono';
import './global.css';

// Per-response CSP nonce from nginx, for runtime <style> injectors (Radix scroll lock); no-op in dev.
applyCspNonce();

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
        <PrivacyProvider>
          <CurrencyProvider>
            <I18nextProvider i18n={i18n}>
              <AiApiProvider api={aiApi}>
                <RouterProvider router={router} />
              </AiApiProvider>
            </I18nextProvider>
          </CurrencyProvider>
        </PrivacyProvider>
      </AuthProvider>
    </QueryClientProvider>
  </StrictMode>
);
