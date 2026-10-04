import { useRechartsTheme } from '@foroba/ui/charts';
import { Area, AreaChart, CartesianGrid, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { useTranslation } from 'react-i18next';
import { useCurrency } from '../contexts/CurrencyContext';
import { usePrivacy } from '../contexts/PrivacyContext';
import { netWorthDomain, signedTick } from '../lib/netWorthAxis';
import { visibleEvents, type NetWorthEvent } from '../lib/netWorthEvents';

interface DataPoint {
  date: string;
  totalEur: number;
}

interface NetWorthChartProps {
  data: DataPoint[];
  events?: NetWorthEvent[];
}

export function NetWorthChart({ data, events = [] }: NetWorthChartProps) {
  const theme = useRechartsTheme();
  const { formatMoney } = useCurrency();
  const { t } = useTranslation();
  const { isPrivate } = usePrivacy();
  const markers = visibleEvents(events, data.map((d) => d.date));

  if (data.length === 0) {
    return (
      <div className="flex h-48 items-center justify-center text-sm text-[var(--color-text-muted)]">
        No historical data yet.
      </div>
    );
  }

  return (
    <>
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
          width="auto"
          domain={netWorthDomain(data)}
          tick={theme.axis.tick}
          axisLine={theme.axis.axisLine}
          tickLine={theme.axis.tickLine}
          tickFormatter={(v: number) => signedTick(v, formatMoney)}
        />
        <Tooltip
          contentStyle={theme.tooltip.contentStyle}
          cursor={theme.tooltip.cursor}
          formatter={(v) => [formatMoney(v as number), 'Net Worth']}
        />
        {markers.map((m) => (
          <ReferenceLine
            key={m.x}
            x={m.x}
            stroke="var(--color-text-muted)"
            strokeDasharray="3 3"
            ifOverflow="hidden"
          >
            <title>{isPrivate ? t('dashboard.eventImportLegend') : t('dashboard.eventImportLabel', { label: m.label })}</title>
          </ReferenceLine>
        ))}
        <Area
          type="monotone"
          dataKey="totalEur"
          stroke={theme.colors[0] as string}
          strokeWidth={2}
          fill="url(#netWorthGrad)"
        />
      </AreaChart>
    </ResponsiveContainer>
    {markers.length > 0 && (
      <p className="mt-2 flex items-center gap-2 text-xs text-[var(--color-text-muted)]">
        <span aria-hidden="true" className="inline-block h-3 border-l border-dashed border-[var(--color-text-muted)]" />
        {t('dashboard.eventImportLegend')}
      </p>
    )}
    </>
  );
}
