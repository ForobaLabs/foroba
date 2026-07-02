import { useQuery } from '@tanstack/react-query';
import { fetchPazuruAccounts, fetchPazuruHealth } from '../api/pazuru';
import { fetchPortfolioPositions, fetchTsumiHealth } from '../api/tsumi';

export function usePazuruHealth() {
  return useQuery({
    queryKey: ['pazuruHealth'],
    queryFn: fetchPazuruHealth,
    refetchInterval: 30_000,
  });
}

export function useTsumiHealth() {
  return useQuery({
    queryKey: ['tsumiHealth'],
    queryFn: fetchTsumiHealth,
    refetchInterval: 30_000,
  });
}

export function useAccountsList() {
  return useQuery({
    queryKey: ['pazuruAccounts'],
    queryFn: fetchPazuruAccounts,
    refetchInterval: 30_000,
  });
}

export function usePortfolioPositions() {
  return useQuery({
    queryKey: ['portfolioPositions'],
    queryFn: fetchPortfolioPositions,
    refetchInterval: 30_000,
  });
}
