import { useGoals } from '@foroba/ui';

export function StreaksWidget() {
  const { goals } = useGoals();
  const streaking = goals.filter((g) => g.status === 'active' && g.weeklyStreak > 0);

  if (streaking.length === 0) return null;

  return (
    <div className="mt-4 rounded-xl border border-[var(--color-border)] bg-[var(--color-bg-card)] p-4">
      <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-[var(--color-text-muted)]">
        Active streaks
      </p>
      <div className="flex flex-wrap gap-2">
        {streaking.map((g) => (
          <span
            key={g.id}
            className="inline-flex items-center gap-1 rounded-full bg-[var(--color-warning)]/15 px-3 py-1 text-xs font-semibold text-[var(--color-warning)]"
          >
            🔥 {g.title} · {g.weeklyStreak}w
          </span>
        ))}
      </div>
    </div>
  );
}
