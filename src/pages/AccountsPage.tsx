import { Badge, Card, CardContent, PageContainer, SectionHeader } from '@foroba/ui';
import { usePazuruHealth } from '../hooks/useServiceHealth';

export function AccountsPage() {
  const health = usePazuruHealth();
  const online = health.data?.status === 'ok';

  return (
    <PageContainer>
      <SectionHeader
        title="Accounts"
        description="Bank accounts & cashflow powered by Pazuru"
        className="mb-6"
      />
      <Card>
        <CardContent className="p-6">
          <div className="flex items-center gap-2 mb-4">
            <span className="text-sm font-medium text-[var(--color-text-primary)]">Pazuru status</span>
            <Badge variant={online ? 'positive' : 'warning'}>
              {online ? 'Connected' : 'Offline'}
            </Badge>
          </div>
          {online ? (
            <p className="text-sm text-[var(--color-text-secondary)]">
              Pazuru is running. The full accounts view will be embedded here in SP3
              when Pazuru adopts <code>@foroba/ui</code>.
            </p>
          ) : (
            <p className="text-sm text-[var(--color-text-muted)]">
              Pazuru is not reachable. Start it at{' '}
              <code className="rounded bg-[var(--color-bg-elevated)] px-1 text-xs">
                {import.meta.env.VITE_PAZURU_API_URL ?? 'http://localhost:8001'}
              </code>{' '}
              to see your accounts here.
            </p>
          )}
        </CardContent>
      </Card>
    </PageContainer>
  );
}
