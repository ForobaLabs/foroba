import { Badge, Card, CardContent, ErrorState, KpiCard, PageContainer, SectionHeader, Skeleton, useUserProfile } from '@foroba/ui';
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { AllocationPie } from '../components/AllocationPie';
import { FinanceTipsCard } from '../components/FinanceTipsCard';
import { NetWorthChart } from '../components/NetWorthChart';
import { ServiceStatusBar } from '../components/ServiceStatusBar';
import { StreaksWidget } from '../components/StreaksWidget';
import { useAuth } from '../auth/AuthProvider';
import { useCurrency } from '../contexts/CurrencyContext';
import { useNetWorth } from '../hooks/useNetWorth';

function greeting(name: string): string {
  const hour = new Date().getHours();
  const salut = hour < 12 ? 'Good morning' : hour < 18 ? 'Good afternoon' : 'Good evening';
  return name ? `${salut}, ${name}` : salut;
}

const SOURCE_LABELS: Record<string, string> = {
  pazuru: 'Pazuru',
  tsumi: 'Tsumi',
};

export function DashboardPage() {
  const navigate = useNavigate();
  const [includeManualAssets, setIncludeManualAssets] = useState(true);
  const { user } = useAuth();
  const { data, isLoading, isError, refetch } = useNetWorth(includeManualAssets, user?.show_debts ?? false);
  const { profile } = useUserProfile();
  const { formatMoney } = useCurrency();

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
              {formatMoney(snapshot?.totalEur ?? 0)}
            </p>
            <div className="mt-1 flex items-center gap-2">
              <Badge variant="default" className="text-xs">
                {new Date().toLocaleDateString(undefined, { dateStyle: 'medium' })}
              </Badge>
              <label className="flex items-center gap-1.5 text-xs text-[var(--color-text-secondary)]">
                <input
                  type="checkbox"
                  checked={includeManualAssets}
                  onChange={(e) => setIncludeManualAssets(e.target.checked)}
                />
                Include manual assets
              </label>
            </div>
          </div>
        )}
      </div>

      {/* Sub KPIs */}
      <div className="mt-6 grid grid-cols-1 gap-4 sm:grid-cols-2">
        <div
          onClick={() => navigate('/accounts')}
          role="button"
          tabIndex={0}
          onKeyDown={(e) => {
            if (e.key === 'Enter') navigate('/accounts');
          }}
          style={{ cursor: 'pointer' }}
        >
          <KpiCard
            label="Cash (Pazuru)"
            value={snapshot ? formatMoney(snapshot.cashEur) : '–'}
            loading={isLoading}
            subtitle="Bank accounts"
          />
        </div>
        <div
          onClick={() => navigate('/portfolio')}
          role="button"
          tabIndex={0}
          onKeyDown={(e) => {
            if (e.key === 'Enter') navigate('/portfolio');
          }}
          style={{ cursor: 'pointer' }}
        >
          <KpiCard
            label="Portfolio (Tsumi)"
            value={snapshot ? formatMoney(snapshot.portfolioEur) : '–'}
            loading={isLoading}
            subtitle="ETF + crypto"
          />
        </div>
        {user?.show_debts && snapshot?.debtsEur !== undefined && (
          <KpiCard
            label="Debts (Pazuru)"
            value={`-${formatMoney(snapshot.debtsEur)}`}
            loading={isLoading}
            subtitle="Manual debts"
          />
        )}
      </div>

      {/* Chart */}
      <Card className="mt-6">
        <CardContent className="p-4">
          <p className="mb-3 text-sm font-medium text-[var(--color-text-secondary)]">
            Net worth over time
          </p>
          <NetWorthChart data={data?.history ?? []} />
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
