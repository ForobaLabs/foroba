import { createContext, useContext, useMemo, type ReactNode } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { formatCurrency } from '@foroba/ui';
import { fetchFxRates } from '../api/foroba';
import { useAuth } from '../auth/AuthProvider';
import { usePrivacy } from './PrivacyContext';

interface CurrencyContextValue {
  displayCurrency: string;
  /** Format an EUR amount into the user's display currency, e.g. "$108.23". */
  formatMoney: (amountEur: number) => string;
  loading: boolean;
}

const Ctx = createContext<CurrencyContextValue>({
  displayCurrency: 'EUR',
  formatMoney: (amountEur) => formatCurrency(amountEur, 'EUR', 'en'),
  loading: true,
});

export function CurrencyProvider({ children }: { children: ReactNode }) {
  const { user } = useAuth();
  const { i18n } = useTranslation();
  const { isPrivate } = usePrivacy();
  const { data, isLoading } = useQuery({
    queryKey: ['fxRates'],
    queryFn: fetchFxRates,
    staleTime: 60 * 60 * 1000, // 1 hour — rates refresh server-side once/day
  });

  const value = useMemo<CurrencyContextValue>(() => {
    const displayCurrency = user?.display_currency ?? 'EUR';
    const rateToEur = displayCurrency === 'EUR' ? 1 : data?.rates[displayCurrency];

    // Locale follows the UI language; hidden amounts honour the shell's privacy toggle everywhere.
    const formatMoney = (amountEur: number): string => {
      const converted = displayCurrency === 'EUR' || !rateToEur ? amountEur : amountEur / rateToEur;
      const currency = displayCurrency === 'EUR' || !rateToEur ? 'EUR' : displayCurrency;
      return formatCurrency(converted, currency, i18n.language, { hidden: isPrivate });
    };

    return { displayCurrency, formatMoney, loading: isLoading };
  }, [user?.display_currency, data, isLoading, i18n.language, isPrivate]);

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

// Hook co-located with its Provider is a standard pattern; splitting into a separate
// file for Fast Refresh purity isn't worth the indirection for a single-line accessor.
// eslint-disable-next-line react-refresh/only-export-components
export const useCurrency = () => useContext(Ctx);
