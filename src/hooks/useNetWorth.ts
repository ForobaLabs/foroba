import { useQuery } from '@tanstack/react-query';
import { fetchNetWorth, type NetWorthResult } from '../api/foroba';

export function useNetWorth() {
  return useQuery<NetWorthResult>({
    queryKey: ['netWorth'],
    queryFn: fetchNetWorth,
    refetchInterval: 60_000,
    staleTime: 30_000,
  });
}
