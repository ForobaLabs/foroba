import { useState } from 'react';
import {
  GoalCard,
  PageContainer,
  SectionHeader,
  SavingsBadge,
  useGoals,
  useUserProfile,
  type GoalCategory,
} from '@foroba/ui';

const CATEGORIES: { value: GoalCategory; label: string }[] = [
  { value: 'savings', label: 'Savings' },
  { value: 'debt', label: 'Debt payoff' },
  { value: 'investment', label: 'Investment' },
  { value: 'emergency_fund', label: 'Emergency fund' },
  { value: 'purchase', label: 'Purchase' },
  { value: 'other', label: 'Other' },
];

const inputCls =
  'mt-1 block w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-bg-primary)] px-3 py-2 text-sm text-[var(--color-text-primary)] focus:outline-none focus:ring-2 focus:ring-[var(--color-accent)]';
const labelCls = 'block text-sm font-medium text-[var(--color-text-secondary)]';

export function GoalsPage() {
  const { goals, addGoal, updateGoal, removeGoal } = useGoals();
  const { profile } = useUserProfile();
  const [showForm, setShowForm] = useState(false);
  const [title, setTitle] = useState('');
  const [category, setCategory] = useState<GoalCategory>('savings');
  const [target, setTarget] = useState('');
  const [current, setCurrent] = useState('0');
  const [targetDate, setTargetDate] = useState('');

  const activeGoals = goals.filter((g) => g.status !== 'completed');
  const doneGoals = goals.filter((g) => g.status === 'completed');

  // Compute total savings rate if we have enough data (placeholder)
  const savingsRate = 18; // will be driven by Pazuru context in SP6+

  const handleAdd = () => {
    if (!title.trim() || !target) return;
    addGoal({
      title: title.trim(),
      category,
      targetAmount: parseFloat(target),
      currentAmount: parseFloat(current) || 0,
      currency: profile.baseCurrency || 'EUR',
      targetDate: targetDate || undefined,
    });
    setTitle(''); setTarget(''); setCurrent('0'); setTargetDate('');
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
              <label className={labelCls}>Category</label>
              <select className={inputCls} value={category} onChange={(e) => setCategory(e.target.value as GoalCategory)}>
                {CATEGORIES.map((c) => <option key={c.value} value={c.value}>{c.label}</option>)}
              </select>
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
          </div>
          <div className="mt-4 flex gap-2">
            <button onClick={handleAdd} className="rounded-lg bg-[var(--color-accent)] px-4 py-2 text-sm font-semibold text-white disabled:opacity-40" disabled={!title.trim() || !target}>
              Save goal
            </button>
            <button onClick={() => setShowForm(false)} className="rounded-lg border border-[var(--color-border)] px-4 py-2 text-sm text-[var(--color-text-secondary)]">
              Cancel
            </button>
          </div>
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
                onClick={() => updateGoal(goal.id, { status: 'completed' })}
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
