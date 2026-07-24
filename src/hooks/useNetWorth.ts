import { useQuery } from '@tanstack/react-query';
import { fetchNetWorth, type NetWorthResult } from '../api/foroba';

export function useNetWorth(includeManualAssets = true, includeDebts = false) {
  return useQuery<NetWorthResult>({
    queryKey: ['netWorth', includeManualAssets, includeDebts],
    queryFn: () => fetchNetWorth(365, includeManualAssets, includeDebts),
    refetchInterval: 60_000,
    staleTime: 30_000,
  });
}
