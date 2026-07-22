import { useQuery } from '@tanstack/react-query';
import { fetchNetWorth, type NetWorthResult } from '../api/foroba';

export function useNetWorth(includeManualAssets = true) {
  return useQuery<NetWorthResult>({
    queryKey: ['netWorth', includeManualAssets],
    queryFn: () => fetchNetWorth(365, includeManualAssets),
    refetchInterval: 60_000,
    staleTime: 30_000,
  });
}
