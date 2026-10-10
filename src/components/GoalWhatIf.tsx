import { useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { formatCurrency } from '@foroba/ui';
import { addMonths, balanceAt, projectGoal, RATE_MAX_PCT } from '../lib/goalProjection';
import { createGoalShare } from '../api/share';

export interface WhatIfGoal {
  title: string;
  targetAmount: number;
  currentAmount: number;
  monthlyContribution?: number;
}

const toCents = (n: number) => Math.round(n * 100);
const rangeCls = 'mt-1 block w-full accent-[var(--color-accent)]';
const labelCls = 'flex items-baseline justify-between text-sm font-medium text-[var(--color-text-secondary)]';

export function GoalWhatIf({ goal, currency, hidden = false }: { goal: WhatIfGoal; currency: string; hidden?: boolean }) {
  const { t, i18n } = useTranslation();
  const lang = i18n.language;
  const baseMonthly = goal.monthlyContribution ?? 0;
  const maxMonthly = Math.max(500, Math.ceil((baseMonthly * 3) / 50) * 50, Math.ceil(goal.targetAmount / 12 / 50) * 50);

  const [monthly, setMonthly] = useState(baseMonthly);
  const [horizon, setHorizon] = useState(24);
  const [rate, setRate] = useState(0);
  const [share, setShare] = useState<{ state: 'idle' | 'busy' | 'done' | 'error'; url?: string }>({ state: 'idle' });

  const projection = useMemo(
    () => projectGoal(toCents(goal.currentAmount), toCents(goal.targetAmount), toCents(monthly), rate),
    [goal.currentAmount, goal.targetAmount, monthly, rate],
  );

  const money = (cents: number) => formatCurrency(cents / 100, currency, lang, { hidden });
  const monthLabel = (offset: number) =>
    addMonths(new Date(), offset).toLocaleDateString(lang, { month: 'long', year: 'numeric' });

  const atHorizon = balanceAt(projection.series, horizon);
  const targetCents = toCents(goal.targetAmount);
  const onTrack = atHorizon >= targetCents;

  const points = projection.series.slice(0, Math.min(projection.series.length, 121));
  const maxY = Math.max(targetCents, ...points, 1);
  const path = points
    .map((v, i) => `${(i / Math.max(points.length - 1, 1)) * 100},${40 - (v / maxY) * 38}`)
    .join(' ');
  const targetY = 40 - (targetCents / maxY) * 38;

  const onShare = async () => {
    setShare({ state: 'busy' });
    try {
      const { path: p } = await createGoalShare({
        name: goal.title,
        currency,
        savedCents: toCents(goal.currentAmount),
        targetCents,
        monthlyCents: toCents(monthly),
        ratePct: rate,
      });
      const url = `${window.location.origin}${p}`;
      try { await navigator.clipboard?.writeText(url); } catch { /* clipboard unavailable: link is shown */ }
      setShare({ state: 'done', url });
    } catch {
      setShare({ state: 'error' });
    }
  };

  return (
    <section
      aria-label={t('goals.whatIf.title', { title: goal.title })}
      className="mt-2 rounded-xl border border-[var(--color-border)] bg-[var(--color-bg-card)] p-4"
    >
      <h3 className="text-sm font-semibold text-[var(--color-text-primary)]">{t('goals.whatIf.heading')}</h3>

      <div className="mt-3 grid gap-4 sm:grid-cols-3">
        <div>
          <label htmlFor={`wi-m-${goal.title}`} className={labelCls}>
            <span>{t('goals.whatIf.monthly')}</span>
            <output className="tabular-nums text-[var(--color-text-primary)]">{money(toCents(monthly))}</output>
          </label>
          <input id={`wi-m-${goal.title}`} type="range" min={0} max={maxMonthly} step={10} value={monthly}
            onChange={(e) => setMonthly(Number(e.target.value))} className={rangeCls} />
        </div>
        <div>
          <label htmlFor={`wi-h-${goal.title}`} className={labelCls}>
            <span>{t('goals.whatIf.date')}</span>
            <output className="text-[var(--color-text-primary)]">{monthLabel(horizon)}</output>
          </label>
          <input id={`wi-h-${goal.title}`} type="range" min={1} max={120} step={1} value={horizon}
            onChange={(e) => setHorizon(Number(e.target.value))} className={rangeCls} />
        </div>
        <div>
          <label htmlFor={`wi-r-${goal.title}`} className={labelCls}>
            <span>{t('goals.whatIf.rate')}</span>
            <output className="tabular-nums text-[var(--color-text-primary)]">{rate.toFixed(1)}%</output>
          </label>
          <input id={`wi-r-${goal.title}`} type="range" min={0} max={RATE_MAX_PCT} step={0.5} value={rate}
            onChange={(e) => setRate(Number(e.target.value))} className={rangeCls} />
        </div>
      </div>

      <p role="status" data-testid="whatif-summary" className="mt-3 text-sm text-[var(--color-text-primary)]">
        {projection.monthsToTarget === null
          ? t('goals.whatIf.never')
          : t('goals.whatIf.reach', { date: monthLabel(projection.monthsToTarget), months: projection.monthsToTarget })}{' '}
        {t(onTrack ? 'goals.whatIf.onTrack' : 'goals.whatIf.short', {
          date: monthLabel(horizon),
          balance: money(atHorizon),
          target: money(targetCents),
        })}
      </p>

      <svg viewBox="0 0 100 40" preserveAspectRatio="none" role="img" aria-label={t('goals.whatIf.chartAria')}
        className="mt-3 h-20 w-full text-[var(--color-accent)]">
        <line x1="0" x2="100" y1={targetY} y2={targetY} stroke="currentColor" strokeOpacity="0.35" strokeDasharray="2 2" vectorEffect="non-scaling-stroke" />
        <polyline points={path} fill="none" stroke="currentColor" strokeWidth="2" vectorEffect="non-scaling-stroke" />
      </svg>

      <div className="mt-3 flex flex-wrap items-center gap-3">
        <button type="button" onClick={() => void onShare()} disabled={share.state === 'busy'}
          className="inline-flex min-h-11 items-center rounded-lg border border-[var(--color-border)] px-4 text-sm text-[var(--color-text-secondary)] hover:bg-[var(--color-bg-elevated)] disabled:opacity-50">
          {t('goals.whatIf.share')}
        </button>
        {share.state === 'done' && (
          <p role="status" className="min-w-0 text-xs text-[var(--color-text-secondary)] [overflow-wrap:anywhere]">
            {t('goals.whatIf.shared')} <span data-testid="share-url">{share.url}</span>
          </p>
        )}
        {share.state === 'error' && <p role="alert" className="text-xs text-[var(--color-negative)]">{t('goals.whatIf.shareError')}</p>}
      </div>
    </section>
  );
}
