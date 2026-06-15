import { AlertCircle, CheckCircle2 } from 'lucide-react';
import { Badge } from '@foroba/ui';
import { usePazuruHealth, useTsumiHealth } from '../hooks/useServiceHealth';

export function ServiceStatusBar() {
  const pazuru = usePazuruHealth();
  const tsumi = useTsumiHealth();

  const pazuruOk = pazuru.data?.status === 'ok';
  const tsumiOk = tsumi.data?.status === 'ok';

  if (pazuruOk && tsumiOk) return null;

  return (
    <div className="flex flex-wrap gap-2 rounded-[var(--radius-md)] border border-[var(--color-warning-subtle)] bg-[var(--color-warning-subtle)] p-3">
      <AlertCircle className="h-4 w-4 shrink-0 text-[var(--color-warning)]" />
      <span className="text-sm text-[var(--color-warning)]">Some services are unavailable:</span>
      {!pazuruOk && (
        <Badge variant="warning">Pazuru offline</Badge>
      )}
      {!tsumiOk && (
        <Badge variant="warning">Tsumi offline</Badge>
      )}
    </div>
  );
}
