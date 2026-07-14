import { useQuery } from '@tanstack/react-query';
import { fetchForobaHealth } from '../api/foroba';
import {
  fetchPazuruAccountDetail,
  fetchPazuruAccounts,
  fetchPazuruAccountTransactions,
  fetchPazuruHealth,
} from '../api/pazuru';
import {
  fetchPortfolioAllocations,
  fetchPortfolioPositions,
  fetchTsumiHealth,
  fetchTsumiSummary,
} from '../api/tsumi';

export function useForobaHealth() {
  return useQuery({
    queryKey: ['forobaHealth'],
    queryFn: fetchForobaHealth,
    refetchInterval: 30_000,
  });
}

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

export function useAccountDetail(accountId: number) {
  return useQuery({
    queryKey: ['pazuruAccountDetail', accountId],
    queryFn: () => fetchPazuruAccountDetail(accountId),
    refetchInterval: 30_000,
  });
}

export function useAccountTransactions(accountId: number) {
  return useQuery({
    queryKey: ['pazuruAccountTransactions', accountId],
    queryFn: () => fetchPazuruAccountTransactions(accountId),
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

export function usePortfolioSummary() {
  return useQuery({
    queryKey: ['portfolioSummary'],
    queryFn: fetchTsumiSummary,
    refetchInterval: 30_000,
  });
}

export function usePortfolioAllocations() {
  return useQuery({
    queryKey: ['portfolioAllocations'],
    queryFn: fetchPortfolioAllocations,
    refetchInterval: 30_000,
  });
}
