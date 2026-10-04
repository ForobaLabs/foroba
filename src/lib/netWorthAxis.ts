const MINUS = '−';

/** Format an axis tick with an explicit minus sign (never rely on a clipped hyphen). */
export function signedTick(value: number, format: (v: number) => string): string {
  const text = format(Math.abs(value));
  // Privacy mode masks amounts; do not leak the sign either.
  if (value >= 0 || !/\d/.test(text)) return value >= 0 ? format(value) : text;
  return `${MINUS}${text}`;
}

/** Y domain derived from the series, padded 8%; does not force zero unless the series spans it. */
export function netWorthDomain(points: { totalEur: number }[]): [number, number] {
  const values = points.map((p) => p.totalEur);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || Math.max(Math.abs(max), 1) * 0.1;
  const pad = span * 0.08;
  return [Math.floor(min - pad), Math.ceil(max + pad)];
}
