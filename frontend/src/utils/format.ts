// Compatibility exports for inactive historical screens. New product code should
// import the explicit helpers from `formatters.ts`.
import { formatCurrency, formatPercent } from './formatters';

export const money = (value?: number) => formatCurrency(value, 'R$ 0,00');
export const pct = (value?: number) => formatPercent(value, 1, '0%');
