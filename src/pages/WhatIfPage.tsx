import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import {
  Area, AreaChart, CartesianGrid, Legend, Line, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts';
import {
  Button, Card, CardContent, ErrorState, LockedFeature, PageContainer, SectionHeader, Spinner,
  useEntitlement,
} from '@foroba/ui';
import { useRechartsTheme } from '@foroba/ui/charts';
import { useAuth } from '../auth/AuthProvider';
import { fetchPazuruGoals, type PazuruGoal } from '../api/pazuru';
import {
  simulateWhatIf, listWhatIfScenarios, createWhatIfScenario, getWhatIfScenario,
  deleteWhatIfScenario,
  type SimulationResult, type WhatIfScenario, type OneOffEvent, type GoalContribution,
} from '../api/whatif';
import { JeliInterpretButton } from '../components/JeliInterpretButton';

const inputCls =
  'mt-1 block w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-bg-primary)] px-3 py-2 text-sm text-[var(--color-text-primary)] focus:outline-none focus:ring-2 focus:ring-[var(--color-accent)]';
const labelCls = 'block text-sm font-medium text-[var(--color-text-secondary)]';

export function WhatIfPage() {
  const { t } = useTranslation();
  const { visible, unlocked } = useEntitlement('household.whatif_simulator');

  if (!visible) return null;

  return (
    <PageContainer>
      <SectionHeader title={t('whatif.title', 'What-If Simulator')} />
      <LockedFeature visible={visible} unlocked={unlocked} label={t('whatif.title', 'What-If Simulator')}>
        <WhatIfBuilder />
      </LockedFeature>
    </PageContainer>
  );
}

function WhatIfBuilder() {
  const { t } = useTranslation();
  const theme = useRechartsTheme();
  const { user } = useAuth();
  const includeDebts = user?.show_debts ?? false;

  const [horizonMonths, setHorizonMonths] = useState(24);
  const [incomeDeltaEur, setIncomeDeltaEur] = useState(0);
  const [investmentGrowthPct, setInvestmentGrowthPct] = useState(5);
  const [eliminateCategoriesInput, setEliminateCategoriesInput] = useState('');
  const [goals, setGoals] = useState<PazuruGoal[]>([]);
  const [goalContributions, setGoalContributions] = useState<GoalContribution[]>([]);
  const [oneOffEvents, setOneOffEvents] = useState<OneOffEvent[]>([]);
  const [result, setResult] = useState<SimulationResult | null>(null);
  const [baselineResult, setBaselineResult] = useState<SimulationResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [scenarioName, setScenarioName] = useState('');
  const [scenarios, setScenarios] = useState<WhatIfScenario[]>([]);

  const baselineDeltaEur = (() => {
    if (!result?.points.length || !baselineResult?.points.length) return null;
    const scenarioTotal = result.points[result.points.length - 1].totalEur;
    const baselineTotal = baselineResult.points[baselineResult.points.length - 1].totalEur;
    return scenarioTotal - baselineTotal;
  })();

  useEffect(() => {
    fetchPazuruGoals().then(setGoals).catch(() => setGoals([]));
    refreshScenarios();
  }, []);

  function refreshScenarios() {
    listWhatIfScenarios().then(setScenarios).catch(() => setScenarios([]));
  }

  function currentParams() {
    return {
      horizonMonths,
      eliminateCategories: eliminateCategoriesInput
        ? eliminateCategoriesInput.split(',').map((s) => s.trim()).filter(Boolean)
        : undefined,
      incomeDeltaCents: Math.round(incomeDeltaEur * 100),
      goalContributions,
      oneOffEvents,
      investmentGrowthRatePct: investmentGrowthPct,
      includeDebts,
    };
  }

  async function run() {
    setLoading(true);
    setError(null);
    try {
      // Sequential (not Promise.all) — firing both requests concurrently trips a
      // backend session-lookup race on the shared connection (returns spurious 401s).
      const scenario = await simulateWhatIf(currentParams());
      const baseline = await simulateWhatIf({ horizonMonths, includeDebts });
      setResult(scenario);
      setBaselineResult(baseline);
    } catch {
      setError(t('whatif.error', 'Simulation failed'));
    } finally {
      setLoading(false);
    }
  }

  function buildJeliContext(): string {
    const lastPoint = result?.points[result.points.length - 1];
    const lines = [
      `Horizon: ${horizonMonths} months`,
      `Projected total net worth at end of horizon: €${lastPoint?.totalEur.toFixed(2) ?? 'n/a'}`,
    ];
    if (baselineDeltaEur !== null) {
      lines.push(
        `Delta vs. baseline (no changes): ${baselineDeltaEur >= 0 ? '+' : ''}€${baselineDeltaEur.toFixed(2)}`,
      );
    }
    if (result?.goalImpacts.length) {
      for (const gi of result.goalImpacts) {
        lines.push(`Goal "${gi.name}": ${gi.newProjection?.projected_date ?? 'no projection'}`);
      }
    }
    return lines.join('\n');
  }

  async function save() {
    if (!scenarioName) return;
    await createWhatIfScenario({ name: scenarioName, horizonMonths, params: currentParams() });
    setScenarioName('');
    refreshScenarios();
  }

  async function load(id: number) {
    const scenario = await getWhatIfScenario(id);
    setHorizonMonths(scenario.horizonMonths);
    setIncomeDeltaEur((scenario.params.incomeDeltaCents ?? 0) / 100);
    setInvestmentGrowthPct(scenario.params.investmentGrowthRatePct ?? 5);
    setEliminateCategoriesInput((scenario.params.eliminateCategories ?? []).join(', '));
    setGoalContributions(scenario.params.goalContributions ?? []);
    setOneOffEvents(scenario.params.oneOffEvents ?? []);
    setResult(scenario.projection);
    setBaselineResult(null);
    simulateWhatIf({ horizonMonths: scenario.horizonMonths, includeDebts })
      .then(setBaselineResult)
      .catch(() => setBaselineResult(null));
  }

  async function remove(id: number) {
    await deleteWhatIfScenario(id);
    refreshScenarios();
  }

  function addOneOffEvent() {
    setOneOffEvents([...oneOffEvents, { monthOffset: 1, amountCents: 0, label: '' }]);
  }

  function toggleGoalContribution(goalId: number) {
    setGoalContributions((prev) =>
      prev.some((c) => c.goalId === goalId)
        ? prev.filter((c) => c.goalId !== goalId)
        : [...prev, { goalId, extraMonthlyCents: 0 }],
    );
  }

  return (
    <div className="space-y-6">
      <Card>
        <CardContent className="space-y-4 p-4">
          <label className={labelCls}>
            {t('whatif.horizon', 'Horizon')}: {horizonMonths} {t('whatif.months', 'months')}
            <input
              type="range" min={1} max={240} value={horizonMonths}
              onChange={(e) => setHorizonMonths(Number(e.target.value))}
              className="mt-1 block w-full"
            />
          </label>

          <label className={labelCls}>
            {t('whatif.eliminateCategories', 'Cut spending in categories (comma-separated)')}
            <input
              value={eliminateCategoriesInput}
              onChange={(e) => setEliminateCategoriesInput(e.target.value)}
              className={inputCls}
              placeholder="dining, entertainment"
            />
          </label>

          <label className={labelCls}>
            {t('whatif.incomeDelta', 'Monthly income change (€)')}
            <input
              type="number" value={incomeDeltaEur}
              onChange={(e) => setIncomeDeltaEur(Number(e.target.value))}
              className={inputCls}
            />
          </label>

          <label className={labelCls}>
            {t('whatif.investmentGrowth', 'Assumed investment growth (%/year)')}
            <input
              type="number" step="0.1" value={investmentGrowthPct}
              onChange={(e) => setInvestmentGrowthPct(Number(e.target.value))}
              className={inputCls}
            />
          </label>

          <div>
            <span className={labelCls}>{t('whatif.goalContributions', 'Extra monthly goal contributions')}</span>
            {goals.map((g) => {
              const contribution = goalContributions.find((c) => c.goalId === g.id);
              return (
                <div key={g.id} className="mt-2 flex items-center gap-2">
                  <input
                    type="checkbox" checked={!!contribution}
                    onChange={() => toggleGoalContribution(g.id)}
                  />
                  <span className="text-sm">{g.name}</span>
                  {contribution && (
                    <input
                      type="number" className={`${inputCls} w-32`}
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

          <div>
            <span className={labelCls}>{t('whatif.oneOffEvents', 'One-off events')}</span>
            {oneOffEvents.map((ev, i) => (
              <div key={i} className="mt-2 flex items-center gap-2">
                <input
                  type="number" placeholder={t('whatif.monthOffset', 'Month')} className={`${inputCls} w-20`}
                  value={ev.monthOffset}
                  onChange={(e) => setOneOffEvents((prev) => prev.map((p, j) => j === i ? { ...p, monthOffset: Number(e.target.value) } : p))}
                />
                <input
                  type="number" placeholder="€" className={`${inputCls} w-28`}
                  value={ev.amountCents / 100}
                  onChange={(e) => setOneOffEvents((prev) => prev.map((p, j) => j === i ? { ...p, amountCents: Math.round(Number(e.target.value) * 100) } : p))}
                />
                <input
                  placeholder={t('whatif.label', 'Label')} className={inputCls}
                  value={ev.label}
                  onChange={(e) => setOneOffEvents((prev) => prev.map((p, j) => j === i ? { ...p, label: e.target.value } : p))}
                />
              </div>
            ))}
            <Button size="sm" onClick={addOneOffEvent} className="mt-2">
              {t('whatif.addEvent', 'Add event')}
            </Button>
          </div>

          <Button onClick={() => void run()} disabled={loading}>
            {loading ? <Spinner size="sm" /> : t('whatif.run', 'Run simulation')}
          </Button>

          {error && <ErrorState message={error} />}
        </CardContent>
      </Card>

      {result && (
        <Card>
          <CardContent className="space-y-4 p-4">
            {result.degraded && (
              <p className="text-sm text-[var(--color-warning)]">
                {t('whatif.degraded', 'Some data sources were unavailable — this projection is partial.')}
              </p>
            )}
            <p className="text-xs text-[var(--color-text-secondary)]">{result.disclaimer}</p>
            {result.debtsEur !== undefined ? (
              <p className="text-xs text-[var(--color-text-secondary)]">
                {t('whatif.debtsIncluded', 'Includes -{{amount}} in outstanding debts (Naforo).', {
                  amount: result.debtsEur.toLocaleString(undefined, { style: 'currency', currency: 'EUR' }),
                })}
              </p>
            ) : (
              <p className="text-xs text-[var(--color-text-secondary)]">
                {t('whatif.debtsExcluded', 'Outstanding debts are not included in this projection. Enable "Show debts" in Settings to include them.')}
              </p>
            )}
            {baselineDeltaEur !== null && (
              <div className="rounded-[var(--radius-md)] border border-[var(--color-border)] bg-[var(--color-surface)] p-3">
                <p className="text-xs text-[var(--color-text-secondary)]">
                  {t('whatif.baselineDelta', 'vs. baseline (no changes)')}
                </p>
                <p
                  className={`text-lg font-semibold ${
                    baselineDeltaEur >= 0 ? 'text-[var(--color-positive)]' : 'text-[var(--color-negative)]'
                  }`}
                >
                  {baselineDeltaEur >= 0 ? '+' : ''}
                  {baselineDeltaEur.toLocaleString(undefined, { style: 'currency', currency: 'EUR' })}
                </p>
              </div>
            )}
            <ResponsiveContainer width="100%" height={320}>
              <AreaChart data={result.points} margin={{ top: 4, right: 4, bottom: 0, left: 0 }}>
                <CartesianGrid {...theme.grid} />
                <XAxis dataKey="month" tick={theme.axis.tick} axisLine={theme.axis.axisLine} tickLine={theme.axis.tickLine} />
                <YAxis tick={theme.axis.tick} axisLine={theme.axis.axisLine} tickLine={theme.axis.tickLine} />
                <Tooltip contentStyle={theme.tooltip.contentStyle} cursor={theme.tooltip.cursor} />
                <Legend />
                <Area type="monotone" dataKey="bankEur" name={t('whatif.bank', 'Bank')} stroke={theme.colors[0] as string} fill={theme.colors[0] as string} fillOpacity={0.15} />
                <Area type="monotone" dataKey="investmentsEur" name={t('whatif.investments', 'Investments')} stroke={theme.colors[1] as string} fill={theme.colors[1] as string} fillOpacity={0.15} />
                <Line type="monotone" dataKey="totalEur" name={t('whatif.total', 'Total')} stroke={theme.colors[2] as string} strokeWidth={2} dot={false} />
              </AreaChart>
            </ResponsiveContainer>
            {result.goalImpacts.map((gi) => (
              <p key={gi.goalId} className="text-sm">
                {gi.name}: {gi.newProjection?.projected_date ?? t('whatif.noProjection', 'no projection')}
              </p>
            ))}
            <JeliInterpretButton contextLabel="Kelen What-If Simulator" buildContext={buildJeliContext} />
          </CardContent>
        </Card>
      )}

      <Card>
        <CardContent className="space-y-3 p-4">
          <span className={labelCls}>{t('whatif.saveScenario', 'Save this scenario')}</span>
          <div className="flex gap-2">
            <input
              value={scenarioName} onChange={(e) => setScenarioName(e.target.value)}
              className={inputCls} placeholder={t('whatif.scenarioName', 'Scenario name')}
            />
            <Button onClick={() => void save()} disabled={!scenarioName}>
              {t('whatif.save', 'Save')}
            </Button>
          </div>
          <ul className="space-y-1">
            {scenarios.map((s) => (
              <li key={s.id} className="flex items-center gap-2 text-sm">
                <button className="underline" onClick={() => void load(s.id)}>{s.name}</button>
                <button className="text-[var(--color-negative)]" onClick={() => void remove(s.id)}>
                  {t('whatif.delete', 'Delete')}
                </button>
              </li>
            ))}
          </ul>
        </CardContent>
      </Card>
    </div>
  );
}
