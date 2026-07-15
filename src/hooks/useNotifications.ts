import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { dismissNotification, fetchNotifications } from '../api/foroba';

export function useNotifications() {
  const qc = useQueryClient();

  const query = useQuery({
    queryKey: ['notifications'],
    queryFn: () => fetchNotifications(),
    refetchInterval: 60_000,
    staleTime: 30_000,
  });

  const dismiss = useMutation({
    mutationFn: (key: string) => dismissNotification(key),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['notifications'] });
    },
  });

  return {
    notifications: query.data?.items ?? [],
    degraded: query.data?.degraded ?? false,
    isLoading: query.isLoading,
    dismiss: (key: string) => { dismiss.mutate(key); },
  };
}
