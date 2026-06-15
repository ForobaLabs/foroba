import { Badge, Card, CardContent, PageContainer, SectionHeader } from '@foroba/ui';
import { useTsumiHealth } from '../hooks/useServiceHealth';

export function PortfolioPage() {
  const health = useTsumiHealth();
  const online = health.data?.status === 'ok';

  return (
    <PageContainer>
      <SectionHeader
        title="Portfolio"
        description="ETF & crypto positions powered by Tsumi"
        className="mb-6"
      />
      <Card>
        <CardContent className="p-6">
          <div className="flex items-center gap-2 mb-4">
            <span className="text-sm font-medium text-[var(--color-text-primary)]">Tsumi status</span>
            <Badge variant={online ? 'positive' : 'warning'}>
              {online ? 'Connected' : 'Offline'}
            </Badge>
          </div>
          {online ? (
            <p className="text-sm text-[var(--color-text-secondary)]">
              Tsumi is running. The full portfolio view will be embedded here in SP3
              when Tsumi migrates its UI to React on <code>@foroba/ui</code>.
            </p>
          ) : (
            <p className="text-sm text-[var(--color-text-muted)]">
              Tsumi is not reachable. Start it at{' '}
              <code className="rounded bg-[var(--color-bg-elevated)] px-1 text-xs">
                {import.meta.env.VITE_TSUMI_API_URL ?? 'http://localhost:8000'}
              </code>{' '}
              to see your portfolio here.
            </p>
          )}
        </CardContent>
      </Card>
    </PageContainer>
  );
}
