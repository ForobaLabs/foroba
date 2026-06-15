import { useUserProfile } from '@foroba/ui';

const TIPS_BY_LEVEL: Record<string, string[]> = {
  novice: [
    'The 50/30/20 rule: 50% needs, 30% wants, 20% savings. Start there.',
    'An emergency fund should cover 3–6 months of expenses. Start small.',
    'Automate your savings: set up a transfer on payday so you never see the money.',
    'Track every expense for one month — awareness is the first step to change.',
  ],
  intermediate: [
    'Index funds beat most active managers over 10+ years — keep costs low.',
    'Maxing out tax-advantaged accounts (401k/ISA/PEA) is free money, use it first.',
    'Dollar-cost averaging removes emotion from investing — invest a fixed amount monthly.',
    'Your savings rate matters more than your investment returns in the early years.',
  ],
  expert: [
    'Asset location matters: hold bonds in tax-deferred accounts, equities in taxable.',
    'Consider sequence-of-returns risk as you approach FIRE — a 5% buffer helps.',
    'Factor tilts (value, small-cap) historically improve long-run risk-adjusted returns.',
    'Tax-loss harvesting can improve after-tax returns by 0.5–1% per year.',
  ],
};

function pickTip(level: string): string {
  const tips = TIPS_BY_LEVEL[level] ?? TIPS_BY_LEVEL.intermediate;
  const idx = new Date().getDate() % tips.length;
  return tips[idx];
}

export function FinanceTipsCard() {
  const { profile } = useUserProfile();
  const tip = pickTip(profile.financeLevel);

  return (
    <div className="mt-4 rounded-xl border border-[var(--color-border)] bg-[var(--color-bg-card)] p-4">
      <p className="mb-1 text-xs font-semibold uppercase tracking-wider text-[var(--color-accent)]">
        Daily tip
      </p>
      <p className="text-sm text-[var(--color-text-primary)]">{tip}</p>
      <p className="mt-1 text-xs text-[var(--color-text-muted)]">
        Tailored to your {profile.financeLevel} level · Ask Jeli for more
      </p>
    </div>
  );
}
