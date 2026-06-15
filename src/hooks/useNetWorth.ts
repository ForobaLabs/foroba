import { useQuery } from '@tanstack/react-query';
import type { NetWorthSnapshot } from '@foroba/ui';
import { fetchNetWorth } from '../api/foroba';

export function useNetWorth() {
  return useQuery<NetWorthSnapshot>({
    queryKey: ['netWorth'],
    queryFn: fetchNetWorth,
    refetchInterval: 60_000,
    staleTime: 30_000,
  });
}
