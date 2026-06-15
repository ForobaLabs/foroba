import { useQuery } from '@tanstack/react-query';
import { fetchPazuruHealth } from '../api/pazuru';
import { fetchTsumiHealth } from '../api/tsumi';

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
