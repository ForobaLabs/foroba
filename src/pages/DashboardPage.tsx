import { Badge, Card, CardContent, EmptyState, ErrorState, KpiCard, PageContainer, SectionHeader, Skeleton, useUserProfile } from '@foroba/ui';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router';
import { AllocationPie } from '../components/AllocationPie';
import { FinanceTipsCard } from '../components/FinanceTipsCard';
import { NetWorthChart } from '../components/NetWorthChart';
import { ServiceStatusBar } from '../components/ServiceStatusBar';
import { StreaksWidget } from '../components/StreaksWidget';
import { useAuth } from '../auth/AuthProvider';
import { useCurrency } from '../contexts/CurrencyContext';
import { useNetWorth } from '../hooks/useNetWorth';

const SOURCE_LABELS: Record<string, string> = {
  pazuru: 'Naforo',
  tsumi: 'Yiriba',
};

const ctaCls =
  'inline-flex min-h-11 items-center rounded-lg bg-[var(--color-accent)] px-4 text-sm font-semibold text-[var(--color-accent-fg,#fff)] hover:opacity-90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-accent)] focus-visible:ring-offset-2';

/** A KPI card that is a real link: keyboard-focusable, announced as a link, no role="button" div. */
function KpiLink({ to, label, children }: { to: string; label: string; children: React.ReactNode }) {
  return (
    <Link
      to={to}
      aria-label={label}
      className="block rounded-xl focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-accent)]"
    >
      {children}
    </Link>
  );
}

export function DashboardPage() {
  const { t, i18n } = useTranslation();
  const [includeManualAssets, setIncludeManualAssets] = useState(true);
  const { user } = useAuth();
  const { data, isLoading, isError, refetch } = useNetWorth(includeManualAssets, user?.show_debts ?? false);
  const { profile } = useUserProfile();
  const { formatMoney } = useCurrency();

  const snapshot = data?.snapshot;
  const degradedSources = data?.degradedSources ?? [];
  const isEmpty =
    !!snapshot &&
    degradedSources.length === 0 &&
    snapshot.totalEur === 0 &&
    snapshot.cashEur === 0 &&
    snapshot.portfolioEur === 0;

  const hour = new Date().getHours();
  const salut = t(`dashboard.greeting.${hour < 12 ? 'morning' : hour < 18 ? 'afternoon' : 'evening'}`);
  const title = profile.name ? t('dashboard.greeting.withName', { greeting: salut, name: profile.name }) : salut;

  const cta = isEmpty ? (
    <Link to="/accounts" className={ctaCls}>{t('dashboard.ctaAddAccount')}</Link>
  ) : (
    <Link to="/goals" className={ctaCls}>{t('dashboard.ctaSetGoal')}</Link>
  );

  return (
    <PageContainer>
      <SectionHeader
        as="h1"
        title={title}
        description={t('dashboard.subtitle')}
        action={isLoading || isError ? undefined : cta}
        className="mb-4"
      />

      <ServiceStatusBar />

      {degradedSources.length > 0 && (
        <div className="mt-4">
          <Badge variant="warning">
            {t('dashboard.partial', { sources: degradedSources.map((s) => SOURCE_LABELS[s] ?? s).join(', ') })}
          </Badge>
        </div>
      )}

      {/* Main KPI */}
      <div className="mt-4">
        {isLoading ? (
          <Skeleton className="h-16 w-64" />
        ) : isError ? (
          <ErrorState
            title={t('dashboard.error.title')}
            message={t('dashboard.error.message')}
            onRetry={() => refetch()}
          />
        ) : isEmpty ? (
          <EmptyState
            title={t('dashboard.empty.title')}
            message={t('dashboard.empty.message')}
            action={<Link to="/accounts" className={ctaCls}>{t('dashboard.empty.action')}</Link>}
          />
        ) : (
          <div>
            <p
              data-testid="net-worth"
              className="font-['JetBrains_Mono',monospace] text-4xl font-bold tabular-nums text-[var(--color-text-primary)]"
            >
              {formatMoney(snapshot?.totalEur ?? 0)}
            </p>
            <div className="mt-1 flex flex-wrap items-center gap-2">
              <Badge variant="default" className="text-xs">
                {new Date().toLocaleDateString(i18n.language, { dateStyle: 'medium' })}
              </Badge>
              <label className="flex min-h-11 items-center gap-1.5 text-xs text-[var(--color-text-secondary)]">
                <input
                  type="checkbox"
                  checked={includeManualAssets}
                  onChange={(e) => setIncludeManualAssets(e.target.checked)}
                />
                {t('dashboard.includeManual')}
              </label>
            </div>
          </div>
        )}
      </div>

      {/* Sub KPIs */}
      {!isEmpty && !isError && (
        <div className="mt-6 grid grid-cols-1 gap-4 sm:grid-cols-2">
          <KpiLink to="/accounts" label={t('dashboard.openAccounts', { label: `${t('dashboard.cash')} (Naforo)` })}>
            <KpiCard
              label={`${t('dashboard.cash')} (Naforo)`}
              value={snapshot ? formatMoney(snapshot.cashEur) : '–'}
              loading={isLoading}
              subtitle={t('dashboard.cashHint')}
            />
          </KpiLink>
          <KpiLink to="/portfolio" label={t('dashboard.openAccounts', { label: `${t('dashboard.portfolio')} (Yiriba)` })}>
            <KpiCard
              label={`${t('dashboard.portfolio')} (Yiriba)`}
              value={snapshot ? formatMoney(snapshot.portfolioEur) : '–'}
              loading={isLoading}
              subtitle={t('dashboard.portfolioHint')}
            />
          </KpiLink>
          {user?.show_debts && snapshot?.debtsEur !== undefined && (
            <KpiCard
              label={`${t('dashboard.debts')} (Naforo)`}
              value={formatMoney(-snapshot.debtsEur)}
              loading={isLoading}
              subtitle={t('dashboard.debtsHint')}
            />
          )}
        </div>
      )}

      {!isEmpty && !isError && (
        <>
          <Card className="mt-6">
            <CardContent className="p-4">
              <h2 className="mb-3 text-sm font-medium text-[var(--color-text-secondary)]">
                {t('dashboard.netWorthOverTime')}
              </h2>
              <NetWorthChart data={data?.history ?? []} events={data?.events ?? []} />
            </CardContent>
          </Card>

          <Card className="mt-4">
            <CardContent className="p-4">
              <h2 className="mb-3 text-sm font-medium text-[var(--color-text-secondary)]">{t('dashboard.allocation')}</h2>
              {snapshot ? (
                <AllocationPie cashEur={snapshot.cashEur} portfolioEur={snapshot.portfolioEur} />
              ) : (
                <Skeleton className="h-32 w-full" />
              )}
            </CardContent>
          </Card>
        </>
      )}

      {/* Goal streaks */}
      <StreaksWidget />

      {/* Daily finance tip */}
      <FinanceTipsCard />
    </PageContainer>
  );
}
