import { useQuery } from '@tanstack/react-query';
import { fetchMarketOverview, fetchMarketSnapshot, type AssetClass } from '../api/markets';

export function useMarketSnapshot(symbol: string, assetClass: AssetClass) {
  return useQuery({
    queryKey: ['marketSnapshot', symbol, assetClass],
    queryFn: () => fetchMarketSnapshot(symbol, assetClass),
    enabled: symbol.trim().length > 0,
    staleTime: 60_000,
  });
}

export function useMarketOverview(assetClass: AssetClass) {
  return useQuery({
    queryKey: ['marketOverview', assetClass],
    queryFn: () => fetchMarketOverview(assetClass),
    staleTime: 60_000,
  });
}
