import { AlertCircle } from 'lucide-react';
import { Badge } from '@foroba/ui';
import { usePazuruHealth, useTsumiHealth } from '../hooks/useServiceHealth';

export function ServiceStatusBar() {
  const pazuru = usePazuruHealth();
  const tsumi = useTsumiHealth();

  // pazuru#149 (PROD-PZR-D03): `data` is undefined during the initial fetch, so
  // computing *Ok before the first result resolves would conflate "still checking"
  // with "confirmed offline" and flash a false warning.
  if (pazuru.isLoading || tsumi.isLoading) return null;

  const pazuruOk = pazuru.data?.status === 'ok';
  const tsumiOk = tsumi.data?.status === 'ok';

  if (pazuruOk && tsumiOk) return null;

  return (
    <div className="flex flex-wrap gap-2 rounded-[var(--radius-md)] border border-[var(--color-warning-subtle)] bg-[var(--color-warning-subtle)] p-3">
      <AlertCircle className="h-4 w-4 shrink-0 text-[var(--color-warning)]" />
      <span className="text-sm text-[var(--color-warning)]">Some services are unavailable:</span>
      {!pazuruOk && (
        <Badge variant="warning">Naforo offline</Badge>
      )}
      {!tsumiOk && (
        <Badge variant="warning">Yiriba offline</Badge>
      )}
    </div>
  );
}
