import { createContext, useContext, useMemo, type ReactNode } from 'react';
import { useQuery } from '@tanstack/react-query';
import { fetchFxRates } from '../api/foroba';
import { useAuth } from '../auth/AuthProvider';

interface CurrencyContextValue {
  displayCurrency: string;
  /** Format an EUR amount into the user's display currency, e.g. "$108.23". */
  formatMoney: (amountEur: number) => string;
  loading: boolean;
}

const Ctx = createContext<CurrencyContextValue>({
  displayCurrency: 'EUR',
  formatMoney: (amountEur) =>
    `€ ${amountEur.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`,
  loading: true,
});

export function CurrencyProvider({ children }: { children: ReactNode }) {
  const { user } = useAuth();
  const { data, isLoading } = useQuery({
    queryKey: ['fxRates'],
    queryFn: fetchFxRates,
    staleTime: 60 * 60 * 1000, // 1 hour — rates refresh server-side once/day
  });

  const value = useMemo<CurrencyContextValue>(() => {
    const displayCurrency = user?.display_currency ?? 'EUR';
    const rateToEur = displayCurrency === 'EUR' ? 1 : data?.rates[displayCurrency];

    const formatMoney = (amountEur: number): string => {
      if (displayCurrency === 'EUR' || !rateToEur) {
        return `€ ${amountEur.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
      }
      const converted = amountEur / rateToEur;
      return converted.toLocaleString('en-US', {
        style: 'currency', currency: displayCurrency,
        minimumFractionDigits: 2, maximumFractionDigits: 2,
      });
    };

    return { displayCurrency, formatMoney, loading: isLoading };
  }, [user?.display_currency, data, isLoading]);

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

// Hook co-located with its Provider is a standard pattern; splitting into a separate
// file for Fast Refresh purity isn't worth the indirection for a single-line accessor.
// eslint-disable-next-line react-refresh/only-export-components
export const useCurrency = () => useContext(Ctx);
