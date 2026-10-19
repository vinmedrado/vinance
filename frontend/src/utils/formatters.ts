export type NumericValue = number | string | null | undefined;

const unavailable = '—';

function parseNumber(value: NumericValue): number | null {
  if (value === null || value === undefined || value === '') return null;
  const normalized = typeof value === 'string' ? value.trim().replace(',', '.') : value;
  const number = Number(normalized);
  return Number.isFinite(number) ? number : null;
}

const currency = new Intl.NumberFormat('pt-BR', {
  style: 'currency',
  currency: 'BRL',
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

export function formatCurrency(value: NumericValue, fallback = unavailable) {
  const number = parseNumber(value);
  return number === null ? fallback : currency.format(number);
}

export function formatDecimal(
  value: NumericValue,
  options: { minimumFractionDigits?: number; maximumFractionDigits?: number; fallback?: string } = {},
) {
  const number = parseNumber(value);
  if (number === null) return options.fallback ?? unavailable;
  return new Intl.NumberFormat('pt-BR', {
    minimumFractionDigits: options.minimumFractionDigits ?? 0,
    maximumFractionDigits: options.maximumFractionDigits ?? 2,
  }).format(number);
}

export function formatInteger(value: NumericValue, fallback = unavailable) {
  const number = parseNumber(value);
  return number === null
    ? fallback
    : new Intl.NumberFormat('pt-BR', { maximumFractionDigits: 0 }).format(number);
}

export function formatCompactNumber(value: NumericValue, fallback = unavailable) {
  const number = parseNumber(value);
  if (number === null) return fallback;
  return new Intl.NumberFormat('pt-BR', {
    notation: 'compact',
    compactDisplay: 'short',
    maximumFractionDigits: Math.abs(number) >= 1_000_000 ? 2 : 1,
  }).format(number);
}

/** Formats a value whose unit is already percentage points (13.75 -> 13,75%). */
export function formatPercent(value: NumericValue, maximumFractionDigits = 2, fallback = unavailable) {
  const number = parseNumber(value);
  return number === null
    ? fallback
    : `${new Intl.NumberFormat('pt-BR', { maximumFractionDigits }).format(number)}%`;
}

/** Formats a ratio/fraction (0.1375 -> 13,75%). Kept explicit to avoid unit guessing. */
export function formatRatioAsPercent(value: NumericValue, maximumFractionDigits = 2, fallback = unavailable) {
  const number = parseNumber(value);
  return number === null ? fallback : formatPercent(number * 100, maximumFractionDigits, fallback);
}

export function formatFinancialRate(value: NumericValue, suffix = 'a.a.', fallback = unavailable) {
  const formatted = formatPercent(value, 2, fallback);
  return formatted === fallback ? fallback : `${formatted} ${suffix}`;
}

export function formatDate(value: string | null | undefined, fallback = unavailable) {
  if (!value) return fallback;
  const civilDate = /^(\d{4})-(\d{2})-(\d{2})/.exec(value);
  if (civilDate) return `${civilDate[3]}/${civilDate[2]}/${civilDate[1]}`;
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? fallback : new Intl.DateTimeFormat('pt-BR').format(date);
}

export function formatDateTime(value: string | null | undefined, fallback = unavailable) {
  if (!value) return fallback;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return fallback;
  return new Intl.DateTimeFormat('pt-BR', {
    dateStyle: 'short',
    timeStyle: 'short',
  }).format(date);
}

export function toNumber(value: NumericValue) {
  return parseNumber(value) ?? 0;
}
