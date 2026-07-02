import { Badge, Card, CardContent, ErrorState, KpiCard, PageContainer, SectionHeader, Skeleton, useUserProfile } from '@foroba/ui';
import { AllocationPie } from '../components/AllocationPie';
import { FinanceTipsCard } from '../components/FinanceTipsCard';
import { NetWorthChart } from '../components/NetWorthChart';
import { ServiceStatusBar } from '../components/ServiceStatusBar';
import { StreaksWidget } from '../components/StreaksWidget';
import { useNetWorth } from '../hooks/useNetWorth';

function greeting(name: string): string {
  const hour = new Date().getHours();
  const salut = hour < 12 ? 'Good morning' : hour < 18 ? 'Good afternoon' : 'Good evening';
  return name ? `${salut}, ${name}` : salut;
}

function fmt(value: number) {
  return value.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

const SOURCE_LABELS: Record<string, string> = {
  pazuru: 'Pazuru',
  tsumi: 'Tsumi',
};

export function DashboardPage() {
  const { data, isLoading, isError, refetch } = useNetWorth();
  const { profile } = useUserProfile();

  const snapshot = data?.snapshot;
  const degradedSources = data?.degradedSources ?? [];

  return (
    <PageContainer>
      <SectionHeader
        title={greeting(profile.name)}
        description="Here's your financial overview"
        className="mb-4"
      />

      <ServiceStatusBar />

      {degradedSources.length > 0 && (
        <div className="mt-4">
          <Badge variant="warning">
            Partial data — {degradedSources.map((s) => SOURCE_LABELS[s] ?? s).join(', ')} unavailable
          </Badge>
        </div>
      )}

      {/* Main KPI */}
      <div className="mt-4">
        {isLoading ? (
          <Skeleton className="h-16 w-64" />
        ) : isError ? (
          <ErrorState message="Failed to load net worth data." onRetry={() => refetch()} />
        ) : (
          <div>
            <p className="font-['JetBrains_Mono',monospace] text-4xl font-bold text-[var(--color-text-primary)]">
              €&thinsp;{fmt(snapshot?.totalEur ?? 0)}
            </p>
            <div className="mt-1 flex items-center gap-2">
              <Badge variant="default" className="text-xs">
                {new Date().toLocaleDateString(undefined, { dateStyle: 'medium' })}
              </Badge>
            </div>
          </div>
        )}
      </div>

      {/* Sub KPIs */}
      <div className="mt-6 grid grid-cols-1 gap-4 sm:grid-cols-2">
        <KpiCard
          label="Cash (Pazuru)"
          value={snapshot ? `€ ${fmt(snapshot.cashEur)}` : '–'}
          loading={isLoading}
          subtitle="Bank accounts"
        />
        <KpiCard
          label="Portfolio (Tsumi)"
          value={snapshot ? `€ ${fmt(snapshot.portfolioEur)}` : '–'}
          loading={isLoading}
          subtitle="ETF + crypto"
        />
      </div>

      {/* Chart */}
      <Card className="mt-6">
        <CardContent className="p-4">
          <p className="mb-3 text-sm font-medium text-[var(--color-text-secondary)]">
            Net worth over time
          </p>
          <NetWorthChart
            data={
              snapshot
                ? [{ date: snapshot.date, totalEur: snapshot.totalEur }]
                : []
            }
          />
        </CardContent>
      </Card>

      {/* Allocation */}
      <Card className="mt-4">
        <CardContent className="p-4">
          <p className="mb-3 text-sm font-medium text-[var(--color-text-secondary)]">Allocation</p>
          {snapshot ? (
            <AllocationPie cashEur={snapshot.cashEur} portfolioEur={snapshot.portfolioEur} />
          ) : (
            <Skeleton className="h-32 w-full" />
          )}
        </CardContent>
      </Card>

      {/* Goal streaks */}
      <StreaksWidget />

      {/* Daily finance tip */}
      <FinanceTipsCard />
    </PageContainer>
  );
}
