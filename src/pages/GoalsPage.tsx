import { useState, useMemo } from 'react';
import {
  GoalCard,
  PageContainer,
  SectionHeader,
  SavingsBadge,
  useGoals,
  useUserProfile,
  suggestTargetDate,
  suggestMonthlyContribution,
} from '@foroba/ui';

const inputCls =
  'mt-1 block w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-bg-primary)] px-3 py-2 text-sm text-[var(--color-text-primary)] focus:outline-none focus:ring-2 focus:ring-[var(--color-accent)]';
const labelCls = 'block text-sm font-medium text-[var(--color-text-secondary)]';

export function GoalsPage() {
  const { goals, addGoal, updateGoal, removeGoal } = useGoals();
  const { profile } = useUserProfile();
  const [showForm, setShowForm] = useState(false);
  const [title, setTitle] = useState('');
  const [target, setTarget] = useState('');
  const [current, setCurrent] = useState('0');
  const [targetDate, setTargetDate] = useState('');
  const [contribution, setContribution] = useState('0');

  const activeGoals = goals.filter((g) => g.status !== 'completed');
  const doneGoals = goals.filter((g) => g.status === 'completed');

  // Compute total savings rate if we have enough data (placeholder)
  const savingsRate = 18; // will be driven by Pazuru context in SP6+

  const targetAmount = parseFloat(target || '0');
  const currentAmount = parseFloat(current || '0');
  const contributionAmount = parseFloat(contribution || '0');
  const hasTarget = targetAmount > 0;
  const hasDeadline = !!targetDate;
  const hasContribution = contributionAmount > 0;

  // Bidirectional live hints
  const suggestion = useMemo(() => {
    if (!hasTarget) return null;
    if (hasContribution && !hasDeadline) {
      const date = suggestTargetDate(targetAmount, currentAmount, contributionAmount);
      return date ? { type: 'date' as const, value: date } : null;
    }
    if (hasDeadline && !hasContribution) {
      const monthly = suggestMonthlyContribution(targetAmount, currentAmount, targetDate);
      return monthly !== null ? { type: 'monthly' as const, value: monthly } : null;
    }
    return null;
  }, [targetAmount, currentAmount, contributionAmount, targetDate, hasTarget, hasDeadline, hasContribution]);

  const handleAdd = () => {
    if (!title.trim() || !target) return;
    addGoal({
      title: title.trim(),
      // Pazuru's Goal model has no category field yet — every goal is
      // 'other' until (if ever) the upstream schema grows one; a selector
      // here would silently discard the choice, which would be worse.
      category: 'other',
      targetAmount: parseFloat(target),
      currentAmount: parseFloat(current) || 0,
      currency: profile.baseCurrency || 'EUR',
      targetDate: targetDate || undefined,
      monthlyContribution: parseFloat(contribution) || 0,
    });
    setTitle(''); setTarget(''); setCurrent('0'); setTargetDate(''); setContribution('0');
    setShowForm(false);
  };

  return (
    <PageContainer>
      <div className="flex items-center justify-between mb-6">
        <SectionHeader
          title="Financial Goals"
          description="Track your progress and build saving streaks"
        />
        <div className="flex items-center gap-3">
          <SavingsBadge savingsRatePct={savingsRate} />
          <button
            onClick={() => setShowForm((v) => !v)}
            className="rounded-lg bg-[var(--color-accent)] px-4 py-2 text-sm font-semibold text-white hover:opacity-90"
          >
            + New goal
          </button>
        </div>
      </div>

      {/* Add goal form */}
      {showForm && (
        <div className="mb-6 rounded-xl border border-[var(--color-border)] bg-[var(--color-bg-card)] p-5">
          <h3 className="mb-4 text-sm font-semibold text-[var(--color-text-primary)]">New goal</h3>
          <div className="grid gap-4 sm:grid-cols-2">
            <div>
              <label className={labelCls}>Title</label>
              <input className={inputCls} value={title} onChange={(e) => setTitle(e.target.value)} placeholder="e.g. Emergency fund" />
            </div>
            <div>
              <label className={labelCls}>Target amount ({profile.baseCurrency})</label>
              <input className={inputCls} type="number" min="0" value={target} onChange={(e) => setTarget(e.target.value)} placeholder="5000" />
            </div>
            <div>
              <label className={labelCls}>Current amount ({profile.baseCurrency})</label>
              <input className={inputCls} type="number" min="0" value={current} onChange={(e) => setCurrent(e.target.value)} placeholder="0" />
            </div>
            <div>
              <label className={labelCls}>Target date (optional)</label>
              <input className={inputCls} type="date" value={targetDate} onChange={(e) => setTargetDate(e.target.value)} />
            </div>
            <div>
              <label className={labelCls}>Monthly contribution ({profile.baseCurrency})</label>
              <input className={inputCls} type="number" min="0" value={contribution} onChange={(e) => setContribution(e.target.value)} placeholder="200" />
            </div>
          </div>
          <div className="mt-4 flex gap-2">
            <button onClick={handleAdd} className="rounded-lg bg-[var(--color-accent)] px-4 py-2 text-sm font-semibold text-white disabled:opacity-40" disabled={!title.trim() || !target}>
              Save goal
            </button>
            <button onClick={() => setShowForm(false)} className="rounded-lg border border-[var(--color-border)] px-4 py-2 text-sm text-[var(--color-text-secondary)]">
              Cancel
            </button>
          </div>

          {suggestion && (
            <div className="mt-3 flex items-center gap-2 rounded-lg border border-[var(--color-accent)]/30 bg-[var(--color-accent)]/5 px-3 py-2 text-sm">
              <span className="inline-flex shrink-0 items-center rounded-full bg-[var(--color-accent)] px-2 py-0.5 text-[11px] font-semibold text-white">
                Suggested
              </span>
              {suggestion.type === 'date' && (
                <span className="text-[var(--color-text-primary)]">
                  At {profile.baseCurrency} {contributionAmount.toFixed(2)}/month you&rsquo;ll reach this goal by{' '}
                  <strong>{suggestion.value as string}</strong>.
                </span>
              )}
              {suggestion.type === 'monthly' && (
                <span className="text-[var(--color-text-primary)]">
                  To hit your {targetDate} deadline, contribute{' '}
                  <strong>{profile.baseCurrency} {(suggestion.value as number).toFixed(2)}/month</strong>.
                </span>
              )}
            </div>
          )}
        </div>
      )}

      {/* Active goals */}
      {activeGoals.length === 0 && !showForm && (
        <div className="rounded-xl border border-dashed border-[var(--color-border)] p-10 text-center">
          <p className="text-sm text-[var(--color-text-muted)]">No active goals yet. Create one to start tracking.</p>
        </div>
      )}
      <div className="space-y-3">
        {activeGoals.map((goal) => (
          <div key={goal.id} className="group relative">
            <GoalCard goal={goal} onUpdate={(g) => updateGoal(g.id, g)} />
            <div className="absolute right-3 top-3 hidden gap-1 group-hover:flex">
              <button
                onClick={() => updateGoal(goal.id, { currentAmount: goal.targetAmount })}
                className="rounded px-2 py-0.5 text-xs font-medium text-[var(--color-positive)] hover:bg-[var(--color-positive)]/10"
              >Done</button>
              <button
                onClick={() => removeGoal(goal.id)}
                className="rounded px-2 py-0.5 text-xs font-medium text-[var(--color-negative)] hover:bg-[var(--color-negative)]/10"
              >Remove</button>
            </div>
          </div>
        ))}
      </div>

      {/* Completed goals */}
      {doneGoals.length > 0 && (
        <div className="mt-8">
          <p className="mb-3 text-xs font-semibold uppercase tracking-wider text-[var(--color-text-muted)]">Completed</p>
          <div className="space-y-3">
            {doneGoals.map((goal) => (
              <div key={goal.id} className="group relative">
                <GoalCard goal={goal} />
                <button
                  onClick={() => removeGoal(goal.id)}
                  className="absolute right-3 top-3 hidden rounded px-2 py-0.5 text-xs text-[var(--color-text-muted)] hover:text-[var(--color-negative)] group-hover:block"
                >Remove</button>
              </div>
            ))}
          </div>
        </div>
      )}
    </PageContainer>
  );
}
