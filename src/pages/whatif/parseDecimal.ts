/**
 * Parses a number typed by a human. Accepts "1.234,5", "1,234.5", "1 234,5", "250 €", "7%" and
 * a typographic minus. When only one separator kind is present it is read by locale: the
 * language's own decimal mark is a decimal; the other mark is a thousands separator only when
 * it forms proper groups of three ("1,234" in English, "1.234" in Italian).
 * Returns NaN for anything that is not unambiguously a number.
 */
export function parseDecimal(raw: string, lang: string): number {
  let s = raw.replace(/[\s\u00a0\u202f\u20ac%]/g, '').replace(/\u2212/g, '-');
  if (!/^-?[\d.,]+$/.test(s)) return NaN;
  const negative = s.startsWith('-');
  if (negative) s = s.slice(1);
  if (!/\d/.test(s)) return NaN;

  const lastDot = s.lastIndexOf('.');
  const lastComma = s.lastIndexOf(',');
  let decimalMark: '.' | ',' | null;
  if (lastDot >= 0 && lastComma >= 0) {
    decimalMark = lastDot > lastComma ? '.' : ',';
  } else if (lastDot >= 0 || lastComma >= 0) {
    const mark = lastDot >= 0 ? '.' : ',';
    const count = s.split(mark).length - 1;
    const localeDecimal = lang.startsWith('en') ? '.' : ',';
    const groupsOfThree = new RegExp(`^\\d{1,3}(\\${mark}\\d{3})+$`).test(s);
    if (count > 1) decimalMark = null;
    else if (mark === localeDecimal) decimalMark = mark;
    else decimalMark = groupsOfThree ? null : mark;
  } else {
    decimalMark = null;
  }

  let normalized: string;
  if (decimalMark === null) {
    if (/[.,]/.test(s) && !/^\d{1,3}([.,]\d{3})+$/.test(s)) return NaN;
    normalized = s.replace(/[.,]/g, '');
  } else {
    const other = decimalMark === '.' ? ',' : '.';
    if (s.split(decimalMark).length > 2) return NaN;
    const [intPart, fracPart] = s.split(decimalMark);
    if (intPart.includes(decimalMark)) return NaN;
    const intDigits = intPart.split(other).join('');
    if (intPart.includes(other) && !new RegExp(`^\\d{1,3}(\\${other}\\d{3})+$`).test(intPart)) return NaN;
    if (!/^\d*$/.test(fracPart ?? '') || !/^\d*$/.test(intDigits)) return NaN;
    normalized = `${intDigits || '0'}.${fracPart ?? ''}`;
  }
  const n = Number(normalized);
  if (!Number.isFinite(n)) return NaN;
  return negative ? -n : n;
}
