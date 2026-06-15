import { Badge, Card, CardContent, KpiCard, PageContainer, SectionHeader, Skeleton } from '@foroba/ui';
import { AllocationPie } from '../components/AllocationPie';
import { NetWorthChart } from '../components/NetWorthChart';
import { ServiceStatusBar } from '../components/ServiceStatusBar';
import { useNetWorth } from '../hooks/useNetWorth';

function fmt(value: number) {
  return value.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

export function DashboardPage() {
  const { data, isLoading, error } = useNetWorth();

  return (
    <PageContainer>
      <SectionHeader title="Net Worth" className="mb-4" />

      <ServiceStatusBar />

      {/* Main KPI */}
      <div className="mt-4">
        {isLoading ? (
          <Skeleton className="h-16 w-64" />
        ) : error ? (
          <p className="text-sm text-[var(--color-negative)]">Failed to load net worth data.</p>
        ) : (
          <div>
            <p className="font-['JetBrains_Mono',monospace] text-4xl font-bold text-[var(--color-text-primary)]">
              €&thinsp;{fmt(data?.totalEur ?? 0)}
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
          value={data ? `€ ${fmt(data.cashEur)}` : '–'}
          loading={isLoading}
          subtitle="Bank accounts"
        />
        <KpiCard
          label="Portfolio (Tsumi)"
          value={data ? `€ ${fmt(data.portfolioEur)}` : '–'}
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
              data
                ? [{ date: data.date, totalEur: data.totalEur }]
                : []
            }
          />
        </CardContent>
      </Card>

      {/* Allocation */}
      <Card className="mt-4">
        <CardContent className="p-4">
          <p className="mb-3 text-sm font-medium text-[var(--color-text-secondary)]">Allocation</p>
          {data ? (
            <AllocationPie cashEur={data.cashEur} portfolioEur={data.portfolioEur} />
          ) : (
            <Skeleton className="h-32 w-full" />
          )}
        </CardContent>
      </Card>
    </PageContainer>
  );
}
