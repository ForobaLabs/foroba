import { useRechartsTheme } from '@foroba/ui/charts';
import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { useCurrency } from '../contexts/CurrencyContext';

interface DataPoint {
  date: string;
  totalEur: number;
}

interface NetWorthChartProps {
  data: DataPoint[];
}

export function NetWorthChart({ data }: NetWorthChartProps) {
  const theme = useRechartsTheme();
  const { formatMoney } = useCurrency();

  if (data.length === 0) {
    return (
      <div className="flex h-48 items-center justify-center text-sm text-[var(--color-text-muted)]">
        No historical data yet.
      </div>
    );
  }

  return (
    <ResponsiveContainer width="100%" height={200}>
      <AreaChart data={data} margin={{ top: 4, right: 4, bottom: 0, left: 0 }}>
        <defs>
          <linearGradient id="netWorthGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor={theme.colors[0] as string} stopOpacity={0.3} />
            <stop offset="95%" stopColor={theme.colors[0] as string} stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid {...theme.grid} />
        <XAxis
          dataKey="date"
          tick={theme.axis.tick}
          axisLine={theme.axis.axisLine}
          tickLine={theme.axis.tickLine}
          tickFormatter={(v: string) => new Date(v).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })}
        />
        <YAxis
          tick={theme.axis.tick}
          axisLine={theme.axis.axisLine}
          tickLine={theme.axis.tickLine}
          tickFormatter={(v: number) => formatMoney(v)}
        />
        <Tooltip
          contentStyle={theme.tooltip.contentStyle}
          cursor={theme.tooltip.cursor}
          formatter={(v) => [formatMoney(v as number), 'Net Worth']}
        />
        <Area
          type="monotone"
          dataKey="totalEur"
          stroke={theme.colors[0] as string}
          strokeWidth={2}
          fill="url(#netWorthGrad)"
        />
      </AreaChart>
    </ResponsiveContainer>
  );
}
