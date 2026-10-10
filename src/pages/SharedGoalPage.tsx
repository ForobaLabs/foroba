import { useQuery } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { useParams } from 'react-router';
import { ErrorState, NotAdvice, Spinner, formatCurrency } from '@foroba/ui';
import { fetchSharedGoal } from '../api/share';
import { addMonths } from '../lib/goalProjection';

/** Public, read-only view of a shared goal what-if. No login, no account data. */
export function SharedGoalPage() {
  const { token = '' } = useParams();
  const { t, i18n } = useTranslation();
  const lang = i18n.language;
  const q = useQuery({ queryKey: ['shared-goal', token], queryFn: () => fetchSharedGoal(token), retry: false });

  if (q.isPending) {
    return <div className="flex min-h-screen items-center justify-center"><Spinner size="lg" /></div>;
  }
  if (q.isError) {
    return (
      <main className="mx-auto max-w-xl px-4 py-16">
        <ErrorState title={t('share.invalidTitle')} message={t('share.invalidMessage')} />
      </main>
    );
  }

  const g = q.data;
  const money = (cents: number) => formatCurrency(cents / 100, g.currency, lang);
  const month = (offset: number) => addMonths(new Date(), offset).toLocaleDateString(lang, { month: 'long', year: 'numeric' });
  const points = g.series.slice(0, 121);
  const maxY = Math.max(g.target_cents, ...points, 1);
  const path = points.map((v, i) => `${(i / Math.max(points.length - 1, 1)) * 100},${40 - (v / maxY) * 38}`).join(' ');
  const targetY = 40 - (g.target_cents / maxY) * 38;

  return (
    <main className="mx-auto max-w-xl px-4 py-10">
      <p className="text-xs uppercase tracking-wider text-[var(--color-text-muted)]">{t('share.eyebrow')}</p>
      <h1 className="mt-1 text-2xl font-semibold text-[var(--color-text-primary)] [overflow-wrap:anywhere]">{g.name}</h1>
      <dl className="mt-4 grid grid-cols-2 gap-3 text-sm">
        <div><dt className="text-[var(--color-text-secondary)]">{t('share.target')}</dt><dd className="tabular-nums">{money(g.target_cents)}</dd></div>
        <div><dt className="text-[var(--color-text-secondary)]">{t('share.saved')}</dt><dd className="tabular-nums">{money(g.saved_cents)}</dd></div>
        <div><dt className="text-[var(--color-text-secondary)]">{t('share.monthly')}</dt><dd className="tabular-nums">{money(g.monthly_cents)}</dd></div>
        <div><dt className="text-[var(--color-text-secondary)]">{t('share.rate')}</dt><dd className="tabular-nums">{g.rate_pct.toFixed(1)}%</dd></div>
      </dl>
      <p className="mt-4 text-sm text-[var(--color-text-primary)]">
        {g.months_to_target === null
          ? t('share.never')
          : t('share.reach', { date: month(g.months_to_target), months: g.months_to_target })}
      </p>
      <svg viewBox="0 0 100 40" preserveAspectRatio="none" role="img" aria-label={t('goals.whatIf.chartAria')}
        className="mt-4 h-28 w-full text-[var(--color-accent)]">
        <line x1="0" x2="100" y1={targetY} y2={targetY} stroke="currentColor" strokeOpacity="0.35" strokeDasharray="2 2" vectorEffect="non-scaling-stroke" />
        <polyline points={path} fill="none" stroke="currentColor" strokeWidth="2" vectorEffect="non-scaling-stroke" />
      </svg>
      <p className="mt-4 text-xs text-[var(--color-text-secondary)]">
        {t('share.expires', { date: new Date(g.exp * 1000).toLocaleDateString(lang, { dateStyle: 'medium' }) })}
      </p>
      <NotAdvice locale={lang} kind="projection" className="mt-4" />
    </main>
  );
}
