import { useEffect, useMemo, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import {
  Area, AreaChart, CartesianGrid, Legend, Line, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts';
import {
  Button, Card, CardContent, ErrorState, LockedFeature, PageContainer, SectionHeader, Spinner,
  formatCurrency, useEntitlement,
} from '@foroba/ui';
import { useRechartsTheme } from '@foroba/ui/charts';
import { useAuth } from '../auth/AuthProvider';
import { usePrivacy } from '../contexts/PrivacyContext';
import { fetchPazuruGoals, type PazuruGoal } from '../api/pazuru';
import {
  listWhatIfScenarios, createWhatIfScenario, getWhatIfScenario, deleteWhatIfScenario,
  type WhatIfScenario, type OneOffEvent, type GoalContribution, type WhatIfParams,
} from '../api/whatif';
import { JeliInterpretButton } from '../components/JeliInterpretButton';
import { useScenarioRun } from './whatif/useScenarioRun';
import { validateScenario, MESSAGES, type ScenarioField, type ScenarioInput } from './whatif/validateScenario';
import { activePreset, DEFAULT_SCENARIO, PRESETS, type PresetId } from './whatif/presets';

const inputCls =
  'mt-1 block w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-bg-primary)] px-3 py-2 text-base text-[var(--color-text-primary)] focus:outline-none focus:ring-2 focus:ring-[var(--color-accent)] aria-[invalid=true]:border-[var(--color-negative)]';
const labelCls = 'block text-sm font-medium text-[var(--color-text-secondary)]';
const helpCls = 'mt-1 text-xs text-[var(--color-text-secondary)]';
const errCls = 'mt-1 text-xs text-[var(--color-negative)]';

export function WhatIfPage() {
  const { t } = useTranslation();
  const { visible, unlocked } = useEntitlement('household.whatif_simulator');

  if (!visible) return null;

  return (
    <PageContainer>
      <SectionHeader as="h1" title={t('whatif.title')} description={t('whatif.subtitle')} />
      <LockedFeature visible={visible} unlocked={unlocked} label={t('whatif.title')}>
        <WhatIfBuilder />
      </LockedFeature>
    </PageContainer>
  );
}

function WhatIfBuilder() {
  const { t, i18n } = useTranslation();
  const lang = i18n.language;
  const theme = useRechartsTheme();
  const { user } = useAuth();
  const { isPrivate } = usePrivacy();
  const includeDebts = user?.show_debts ?? false;

  const [input, setInput] = useState<ScenarioInput>(DEFAULT_SCENARIO);
  const [eliminateCategoriesInput, setEliminateCategoriesInput] = useState('');
  const [goals, setGoals] = useState<PazuruGoal[]>([]);
  const [goalContributions, setGoalContributions] = useState<GoalContribution[]>([]);
  const [oneOffEvents, setOneOffEvents] = useState<OneOffEvent[]>([]);
  const [scenarioName, setScenarioName] = useState('');
  const [scenarios, setScenarios] = useState<WhatIfScenario[]>([]);
  const fieldRefs = useRef<Partial<Record<ScenarioField, HTMLInputElement | null>>>({});

  const validation = useMemo(() => validateScenario(input, lang), [input, lang]);

  function paramsFor(values: { amount: number; years: number; rate: number }): WhatIfParams {
    const categories = eliminateCategoriesInput.split(',').map((s) => s.trim()).filter(Boolean);
    return {
      horizonMonths: values.years * 12,
      eliminateCategories: categories.length ? categories : undefined,
      incomeDeltaCents: Math.round(values.amount * 100),
      goalContributions,
      oneOffEvents,
      investmentGrowthRatePct: values.rate,
      includeDebts,
    };
  }

  const params = validation.values ? paramsFor(validation.values) : null;
  const { result, baseline, loading, failed, runNow } = useScenarioRun(params);

  useEffect(() => {
    fetchPazuruGoals().then(setGoals).catch(() => setGoals([]));
    refreshScenarios();
  }, []);

  function refreshScenarios() {
    listWhatIfScenarios().then(setScenarios).catch(() => setScenarios([]));
  }

  function setField(field: ScenarioField, value: string) {
    setInput((prev) => ({ ...prev, [field]: value }));
  }

  function run() {
    if (validation.firstInvalid) {
      fieldRefs.current[validation.firstInvalid]?.focus();
      return;
    }
    runNow();
  }

  const money = (v: number) => formatCurrency(v, 'EUR', lang, { hidden: isPrivate, maximumFractionDigits: 0 });
  const lastPoint = result?.points[result.points.length - 1];
  const baselineLast = baseline?.points[baseline.points.length - 1];
  const delta = lastPoint && baselineLast ? lastPoint.totalEur - baselineLast.totalEur : null;
  const years = validation.values?.years ?? Number(input.years);
  const preset = activePreset(input);

  function buildJeliContext(): string {
    const lines = [
      `Horizon: ${years} years`,
      `Projected total net worth at end of horizon: €${lastPoint?.totalEur.toFixed(2) ?? 'n/a'}`,
    ];
    if (delta !== null) lines.push(`Delta vs. baseline (no changes): ${delta >= 0 ? '+' : ''}€${delta.toFixed(2)}`);
    for (const gi of result?.goalImpacts ?? []) {
      lines.push(`Goal "${gi.name}": ${gi.newProjection?.projected_date ?? 'no projection'}`);
    }
    return lines.join('\n');
  }

  async function save() {
    if (!scenarioName || !validation.values) return;
    const p = paramsFor(validation.values);
    await createWhatIfScenario({ name: scenarioName, horizonMonths: p.horizonMonths, params: p });
    setScenarioName('');
    refreshScenarios();
  }

  async function load(id: number) {
    const scenario = await getWhatIfScenario(id);
    const delta = (scenario.params.incomeDeltaCents ?? 0) / 100;
    setInput({
      amount: String(delta),
      years: String(Math.max(1, Math.round(scenario.horizonMonths / 12))),
      rate: String(scenario.params.investmentGrowthRatePct ?? 5),
    });
    setEliminateCategoriesInput((scenario.params.eliminateCategories ?? []).join(', '));
    setGoalContributions(scenario.params.goalContributions ?? []);
    setOneOffEvents(scenario.params.oneOffEvents ?? []);
  }

  async function remove(id: number) {
    await deleteWhatIfScenario(id);
    refreshScenarios();
  }

  function toggleGoalContribution(goalId: number) {
    setGoalContributions((prev) =>
      prev.some((c) => c.goalId === goalId)
        ? prev.filter((c) => c.goalId !== goalId)
        : [...prev, { goalId, extraMonthlyCents: 0 }],
    );
  }

  const field = (id: ScenarioField, label: string, help: string) => {
    const err = validation.errors[id];
    return (
      <div>
        <label htmlFor={`whatif-${id}`} className={labelCls}>{label}</label>
        <input
          id={`whatif-${id}`}
          ref={(el) => { fieldRefs.current[id] = el; }}
          type="text"
          inputMode="decimal"
          autoComplete="off"
          value={input[id]}
          onChange={(e) => setField(id, e.target.value)}
          aria-invalid={err ? true : undefined}
          aria-describedby={`whatif-${id}-${err ? 'err' : 'help'}`}
          className={inputCls}
        />
        {err ? (
          <p id={`whatif-${id}-err`} className={errCls}>{t(`whatif.errors.${err}`, MESSAGES[err])}</p>
        ) : (
          <p id={`whatif-${id}-help`} className={helpCls}>{help}</p>
        )}
      </div>
    );
  };

  return (
    <div className="space-y-6">
      <div className="grid gap-6 lg:grid-cols-2 lg:items-start">
        <Card>
          <CardContent className="space-y-4 p-4">
            <div>
              <span className={labelCls} id="whatif-presets">{t('whatif.presetsLabel')}</span>
              <div role="group" aria-labelledby="whatif-presets" className="mt-2 flex flex-wrap gap-2">
                {(Object.keys(PRESETS) as PresetId[]).map((id) => (
                  <button
                    key={id}
                    type="button"
                    aria-pressed={preset === id}
                    onClick={() => setInput({ ...PRESETS[id] })}
                    className="min-h-11 rounded-full border border-[var(--color-border)] px-4 text-sm aria-pressed:border-[var(--color-accent)] aria-pressed:bg-[var(--color-accent)] aria-pressed:text-white"
                  >
                    {t(`whatif.presets.${id}`)}
                  </button>
                ))}
              </div>
            </div>

            {field('amount', t('whatif.amountLabel'), t('whatif.amountHelp'))}
            {field('years', t('whatif.yearsLabel'), t('whatif.yearsHelp'))}
            {field('rate', t('whatif.rateLabel'), t('whatif.rateHelp'))}

            <details className="rounded-lg border border-[var(--color-border)] p-3">
              <summary className="min-h-11 cursor-pointer text-sm font-medium leading-[2.75rem]">{t('whatif.advanced')}</summary>
              <div className="space-y-4 pt-2">
                <label className={labelCls}>
                  {t('whatif.eliminateCategories')}
                  <input
                    value={eliminateCategoriesInput}
                    onChange={(e) => setEliminateCategoriesInput(e.target.value)}
                    className={inputCls}
                    placeholder="dining, entertainment"
                  />
                </label>

                {goals.length > 0 && (
                  <div>
                    <span className={labelCls}>{t('whatif.goalContributions')}</span>
                    {goals.map((g) => {
                      const contribution = goalContributions.find((c) => c.goalId === g.id);
                      return (
                        <div key={g.id} className="mt-2 flex items-center gap-2">
                          <input
                            type="checkbox" checked={!!contribution} aria-label={g.name}
                            onChange={() => toggleGoalContribution(g.id)}
                            className="size-5"
                          />
                          <span className="min-w-0 break-words text-sm">{g.name}</span>
                          {contribution && (
                            <input
                              type="number" className={`${inputCls} w-32`} aria-label={`${g.name} €`}
                              value={contribution.extraMonthlyCents / 100}
                              onChange={(e) =>
                                setGoalContributions((prev) =>
                                  prev.map((c) => c.goalId === g.id ? { ...c, extraMonthlyCents: Math.round(Number(e.target.value) * 100) } : c),
                                )
                              }
                            />
                          )}
                        </div>
                      );
                    })}
                  </div>
                )}

                <div>
                  <span className={labelCls}>{t('whatif.oneOffEvents')}</span>
                  {oneOffEvents.map((ev, i) => (
                    <div key={i} className="mt-2 flex flex-wrap items-center gap-2">
                      <input
                        type="number" placeholder={t('whatif.monthOffset')} aria-label={t('whatif.monthOffset')}
                        className={`${inputCls} w-20`} value={ev.monthOffset}
                        onChange={(e) => setOneOffEvents((prev) => prev.map((p, j) => j === i ? { ...p, monthOffset: Number(e.target.value) } : p))}
                      />
                      <input
                        type="number" placeholder="€" aria-label="€" className={`${inputCls} w-28`}
                        value={ev.amountCents / 100}
                        onChange={(e) => setOneOffEvents((prev) => prev.map((p, j) => j === i ? { ...p, amountCents: Math.round(Number(e.target.value) * 100) } : p))}
                      />
                      <input
                        placeholder={t('whatif.label')} aria-label={t('whatif.label')} className={`${inputCls} min-w-0 flex-1`}
                        value={ev.label}
                        onChange={(e) => setOneOffEvents((prev) => prev.map((p, j) => j === i ? { ...p, label: e.target.value } : p))}
                      />
                    </div>
                  ))}
                  <Button
                    size="sm" className="mt-2"
                    onClick={() => setOneOffEvents([...oneOffEvents, { monthOffset: 1, amountCents: 0, label: '' }])}
                  >
                    {t('whatif.addEvent')}
                  </Button>
                </div>
              </div>
            </details>

            <Button onClick={run} disabled={loading}>
              {loading ? <Spinner size="sm" /> : t('whatif.run')}
            </Button>
          </CardContent>
        </Card>

        <div className="space-y-4">
          {failed && (
            <Card>
              <CardContent className="p-0">
                <ErrorState message={t('whatif.error')} onRetry={runNow} retryLabel={t('whatif.retry')} />
              </CardContent>
            </Card>
          )}
          {lastPoint ? (
            <Card>
              <CardContent className="space-y-4 p-4">
                <div
                  aria-live="polite"
                  className="sticky bottom-20 z-10 rounded-[var(--radius-md)] border border-[var(--color-border)] bg-[var(--color-surface)] p-3 shadow-md lg:static lg:shadow-none"
                >
                  <p className="text-xs text-[var(--color-text-secondary)]">
                    {t('whatif.summaryEnd', { years })}{loading ? ` · ${t('whatif.updating')}` : ''}
                  </p>
                  <p className="text-2xl font-semibold tabular-nums">{money(lastPoint.totalEur)}</p>
                  {delta !== null && (
                    <p className={`text-sm tabular-nums ${delta >= 0 ? 'text-[var(--color-positive)]' : 'text-[var(--color-negative)]'}`}>
                      {delta >= 0 ? '+' : ''}{money(delta)} {t('whatif.vsBaseline')}
                    </p>
                  )}
                </div>
                {result?.degraded && (
                  <p className="text-sm text-[var(--color-warning)]">{t('whatif.degraded')}</p>
                )}
                <ResponsiveContainer width="100%" height={320}>
                  <AreaChart data={result?.points} margin={{ top: 4, right: 4, bottom: 0, left: 0 }}>
                    <CartesianGrid {...theme.grid} />
                    <XAxis
                      dataKey="month" tick={theme.axis.tick} axisLine={theme.axis.axisLine} tickLine={theme.axis.tickLine}
                      tickFormatter={(m: number) => `${Math.round((m / 12) * 10) / 10}`}
                      label={{ value: t('whatif.yearsAxis'), position: 'insideBottomRight', offset: -2 }}
                    />
                    <YAxis tick={theme.axis.tick} axisLine={theme.axis.axisLine} tickLine={theme.axis.tickLine} hide={isPrivate} />
                    <Tooltip contentStyle={theme.tooltip.contentStyle} cursor={theme.tooltip.cursor} />
                    <Legend />
                    <Area type="monotone" dataKey="bankEur" name={t('whatif.bank')} stroke={theme.colors[0] as string} fill={theme.colors[0] as string} fillOpacity={0.15} />
                    <Area type="monotone" dataKey="investmentsEur" name={t('whatif.investments')} stroke={theme.colors[1] as string} fill={theme.colors[1] as string} fillOpacity={0.15} />
                    <Line type="monotone" dataKey="totalEur" name={t('whatif.total')} stroke={theme.colors[2] as string} strokeWidth={2} dot={false} />
                  </AreaChart>
                </ResponsiveContainer>
                {result?.goalImpacts.map((gi) => (
                  <p key={gi.goalId} className="break-words text-sm">
                    {gi.name}: {gi.newProjection?.projected_date ?? t('whatif.noProjection')}
                  </p>
                ))}
                {result?.debtsEur !== undefined ? (
                  <p className="text-xs text-[var(--color-text-secondary)]">
                    {t('whatif.debtsIncluded', { amount: money(result.debtsEur) })}
                  </p>
                ) : (
                  <p className="text-xs text-[var(--color-text-secondary)]">{t('whatif.debtsExcluded')}</p>
                )}
                <p className="text-xs text-[var(--color-text-secondary)]">{result?.disclaimer}</p>
                <JeliInterpretButton contextLabel="Kelen What-If Simulator" buildContext={buildJeliContext} />
              </CardContent>
            </Card>
          ) : (
            !failed && (
              <Card>
                <CardContent className="flex items-center gap-2 p-4 text-sm text-[var(--color-text-secondary)]" role="status">
                  <Spinner size="sm" /> {t('whatif.updating')}
                </CardContent>
              </Card>
            )
          )}
        </div>
      </div>

      <Card>
        <CardContent className="space-y-3 p-4">
          <label htmlFor="whatif-scenario-name" className={labelCls}>{t('whatif.saveScenario')}</label>
          <div className="flex gap-2">
            <input
              id="whatif-scenario-name" value={scenarioName} onChange={(e) => setScenarioName(e.target.value)}
              className={inputCls} placeholder={t('whatif.scenarioName')}
            />
            <Button onClick={() => void save()} disabled={!scenarioName || !validation.values}>
              {t('whatif.save')}
            </Button>
          </div>
          <ul className="space-y-1">
            {scenarios.map((s) => (
              <li key={s.id} className="flex flex-wrap items-center gap-3 text-sm">
                <button className="min-h-11 break-words text-left underline" onClick={() => void load(s.id)}>{s.name}</button>
                <button className="min-h-11 text-[var(--color-negative)]" onClick={() => void remove(s.id)}>
                  {t('whatif.delete')}
                </button>
              </li>
            ))}
          </ul>
        </CardContent>
      </Card>
    </div>
  );
}
