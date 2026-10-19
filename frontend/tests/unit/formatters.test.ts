import { describe, expect, test } from 'vitest';
import {
  formatCompactNumber,
  formatCurrency,
  formatDate,
  formatDateTime,
  formatDecimal,
  formatFinancialRate,
  formatInteger,
  formatPercent,
  formatRatioAsPercent,
} from '../../src/utils/formatters';

describe('formatadores PT-BR', () => {
  test('não transforma dado ausente em zero', () => {
    expect(formatCurrency(null)).toBe('—');
    expect(formatPercent(undefined)).toBe('—');
    expect(formatDecimal('')).toBe('—');
  });

  test('formata dinheiro, números e percentuais com semântica explícita', () => {
    expect(formatCurrency('5000')).toMatch(/R\$\s5\.000,00/);
    expect(formatPercent('13.750000')).toBe('13,75%');
    expect(formatRatioAsPercent('0.0082')).toBe('0,82%');
    expect(formatFinancialRate('6.800000')).toBe('6,8% a.a.');
    expect(formatDecimal('0.050788', { maximumFractionDigits: 4 })).toBe('0,0508');
    expect(formatInteger('27821014')).toBe('27.821.014');
  });

  test('compacta valores grandes sem casas artificiais', () => {
    expect(formatCompactNumber('27821014')).toMatch(/^27,82\s?mi$/i);
  });

  test('mantém data civil independente do fuso da máquina', () => {
    expect(formatDate('2026-10-15')).toBe('15/10/2026');
    expect(formatDate('invalid')).toBe('—');
    expect(formatDateTime('invalid')).toBe('—');
  });
});
