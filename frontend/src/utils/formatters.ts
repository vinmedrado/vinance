export const currency = new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' });
export const percent = new Intl.NumberFormat('pt-BR', { maximumFractionDigits: 2 });

export function formatCurrency(value: number | string | null | undefined) {
  const normalized = Number(value ?? 0);
  return currency.format(Number.isFinite(normalized) ? normalized : 0);
}

export function formatPercent(value: number | string | null | undefined) {
  const normalized = Number(value ?? 0);
  return `${percent.format(Number.isFinite(normalized) ? normalized : 0)}%`;
}

export function toNumber(value: number | string | null | undefined) {
  const normalized = Number(value ?? 0);
  return Number.isFinite(normalized) ? normalized : 0;
}
