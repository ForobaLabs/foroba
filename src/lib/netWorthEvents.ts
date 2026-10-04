export interface NetWorthEvent {
  date: string;
  label: string;
  kind: 'import';
}

export interface VisibleEvent extends NetWorthEvent {
  /** The chart x value (a date present in the series) the marker is drawn on. */
  x: string;
}

/**
 * Events that can be drawn on the chart: each is snapped to the first series date on or
 * after it, and dropped when it falls outside the series. Events sharing a snapped date
 * collapse into one marker, keeping the latest label.
 */
export function visibleEvents(events: NetWorthEvent[], seriesDates: string[]): VisibleEvent[] {
  if (seriesDates.length === 0) return [];
  const sorted = [...seriesDates].sort();
  const first = sorted[0];
  const last = sorted[sorted.length - 1];
  const byX = new Map<string, VisibleEvent>();
  for (const ev of [...events].sort((a, b) => a.date.localeCompare(b.date))) {
    if (ev.date < first || ev.date > last) continue;
    const x = sorted.find((d) => d >= ev.date);
    if (x) byX.set(x, { ...ev, x });
  }
  return [...byX.values()];
}
