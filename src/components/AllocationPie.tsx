import { useRechartsTheme } from '@foroba/ui/charts';
import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from 'recharts';

interface AllocationPieProps {
  cashEur: number;
  portfolioEur: number;
}

export function AllocationPie({ cashEur, portfolioEur }: AllocationPieProps) {
  const theme = useRechartsTheme();
  const total = cashEur + portfolioEur;

  if (total === 0) {
    return (
      <div className="flex h-32 items-center justify-center text-sm text-[var(--color-text-muted)]">
        No data to display.
      </div>
    );
  }

  const data = [
    { name: 'Cash (Pazuru)', value: cashEur },
    { name: 'Portfolio (Tsumi)', value: portfolioEur },
  ];

  return (
    <div className="flex items-center gap-4">
      <ResponsiveContainer width={120} height={120}>
        <PieChart>
          <Pie data={data} dataKey="value" innerRadius={30} outerRadius={50} paddingAngle={3}>
            {data.map((_, i) => (
              <Cell key={i} fill={theme.colors[i] as string} />
            ))}
          </Pie>
          <Tooltip
            contentStyle={theme.tooltip.contentStyle}
            formatter={(v) => `€${(v as number).toLocaleString('en-US', { minimumFractionDigits: 0 })}`}
          />
        </PieChart>
      </ResponsiveContainer>
      <div className="flex flex-col gap-1">
        {data.map((item, i) => (
          <div key={i} className="flex items-center gap-2 text-xs">
            <span
              className="h-2.5 w-2.5 rounded-full"
              style={{ background: theme.colors[i] as string }}
            />
            <span className="text-[var(--color-text-secondary)]">{item.name}</span>
            <span className="font-mono font-medium text-[var(--color-text-primary)]">
              {total > 0 ? `${((item.value / total) * 100).toFixed(1)}%` : '–'}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
