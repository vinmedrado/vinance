import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest';
import { MarketPage } from '../../src/pages/MarketPage';

const market = vi.hoisted(() => ({
  macro: vi.fn(),
  fixedIncome: vi.fn(),
  fundamentals: vi.fn(),
}));

vi.mock('../../src/features/market/hooks/useMarket', () => ({
  useMacroIndicators: () => market.macro(),
  useRendaFixa: () => market.fixedIncome(),
  useFundamentals: (kind: string, query: unknown) => market.fundamentals(kind, query),
}));

function success(data: unknown) {
  return { data, isLoading: false, error: null };
}

beforeEach(() => {
  market.macro.mockReturnValue(success({ items: [
    { id: 1, code: 'CDI', name: 'CDI diário', date: '2026-10-14', value: '0.049000', source: 'bcb' },
    { id: 2, code: 'CDI', name: 'CDI diário', date: '2026-10-15', value: '0.050788', source: 'bcb' },
    { id: 3, code: 'SELIC', name: 'Taxa Selic Meta', date: '2026-10-15', value: '13.750000', source: 'bcb' },
  ], total: 3 }));
  market.fixedIncome.mockReturnValue(success({ items: [{
    id: 14,
    source_product_id: 'tesouro-educa:2043-12-15',
    nome: 'Tesouro Educa+ 2043',
    indexador: 'IPCA',
    purchase_rate: '6.740000',
    taxa_total_equiv: '6.860000',
    investimento_minimo: '18.46',
    vencimento: '2043-12-15',
    liquidity_type: 'DAILY_REPURCHASE',
    source: 'tesouro_transparente',
  }], total: 1 }));
  market.fundamentals.mockImplementation((kind: string) => success({
    items: kind === 'cripto' ? [{
      id: 7,
      coin_id: 'coin98',
      ticker: 'C98',
      name: 'Coin98',
      date: '2026-10-17',
      price_brl: '0.26686900',
      price_change_24h_pct: '-2.817560',
      market_cap_usd: '79704177.000000',
      volume_24h_usd: '46956260.000000',
      source: 'COINGECKO',
    }] : kind === 'bdr' ? [{
      id: 8,
      ticker: 'AAPL34',
      name: 'Apple BDR',
      date: '2026-10-17',
      price: '83.12',
      dy_12m: '0.64',
      volume_medio_diario_brl: '1875000',
      source: 'INVESTIDOR10',
    }] : [],
    total: ['cripto', 'bdr'].includes(kind) ? 1 : 0,
  }));
});

afterEach(() => {
  vi.useRealTimers();
});

describe('Mercado', () => {
  test('exibe a última observação de cada indicador e formata dados reais', () => {
    render(<MarketPage />);

    expect(screen.queryByText('0.049000')).not.toBeInTheDocument();
    expect(screen.getAllByText('0,05%').length).toBeGreaterThan(0);
    expect(screen.getAllByText('13,75%').length).toBeGreaterThan(0);
    expect(screen.getAllByText('IPCA + 6,74% a.a.').length).toBeGreaterThan(0);
    expect(screen.getAllByText('15/12/2043').length).toBeGreaterThan(0);
  });

  test('diferencia ausência real de dados e apresenta Cripto sem números crus', async () => {
    render(<MarketPage />);

    expect(screen.getByText('Dados ainda não disponíveis')).toBeInTheDocument();
    await userEvent.click(screen.getByRole('tab', { name: 'Cripto' }));

    expect(screen.getAllByText('C98').length).toBeGreaterThan(0);
    expect(screen.getAllByText(/R\$\s0,27/).length).toBeGreaterThan(0);
    expect(screen.getAllByText('-2,82%').length).toBeGreaterThan(0);
    expect(screen.queryByText('79704177.000000')).not.toBeInTheDocument();
    expect(screen.getAllByText(/US\$\s79,7\s?mi/i).length).toBeGreaterThan(0);
  });

  test('permite navegar pelas abas com teclado', async () => {
    render(<MarketPage />);
    const first = screen.getByRole('tab', { name: 'FIIs' });
    first.focus();
    await userEvent.keyboard('{ArrowRight}');
    expect(screen.getByRole('tab', { name: 'Ações' })).toHaveAttribute('aria-selected', 'true');
  });

  test('usa o contrato de volume e dividend yield do BDR', async () => {
    render(<MarketPage />);
    await userEvent.click(screen.getByRole('tab', { name: 'BDRs' }));

    expect(screen.getAllByText('AAPL34').length).toBeGreaterThan(0);
    expect(screen.getAllByText('1,88 mi').length).toBeGreaterThan(0);
    expect(screen.getAllByText('0,64%').length).toBeGreaterThan(0);
    expect(screen.queryByRole('columnheader', { name: 'Retorno (12m)' })).not.toBeInTheDocument();
  });

  test('busca e pagina pelo total lógico de ativos', async () => {
    const items = Array.from({ length: 20 }, (_, index) => ({
      id: index + 1,
      ticker: `FII${String(index + 1).padStart(2, '0')}11`,
      name: `Fundo ${index + 1}`,
      date: '2026-10-17',
      price: '100.00',
      source: 'INVESTIDOR10',
    }));
    market.fundamentals.mockImplementation((_kind: string, query: { offset?: number; search?: string }) => success({
      items,
      total: 43,
      limit: 20,
      offset: query.offset ?? 0,
    }));
    render(<MarketPage />);

    expect(screen.getByText('1–20 de 43 ativos')).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Próxima' }));
    expect(market.fundamentals).toHaveBeenLastCalledWith('fii', expect.objectContaining({ offset: 20, limit: 20 }));

    const search = screen.getByRole('searchbox', { name: 'Buscar fundos imobiliários' });
    await userEvent.type(search, 'XPML11');
    await userEvent.click(screen.getByRole('button', { name: 'Buscar' }));
    expect(market.fundamentals).toHaveBeenLastCalledWith('fii', expect.objectContaining({ offset: 0, search: 'XPML11' }));
  });

  test('não apresenta o horizonte futuro da série Selic como previsão', () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date('2026-10-18T12:00:00-03:00'));
    market.macro.mockReturnValue(success({ items: [{
      id: 4,
      code: 'SELIC',
      name: 'Taxa Selic Meta',
      date: '2026-11-04',
      value: '13.750000',
      source: 'bcb',
    }], total: 1 }));

    render(<MarketPage />);

    expect(screen.getAllByText('Meta Selic vigente. A data indica o período de referência do Banco Central.').length).toBeGreaterThan(0);
    expect(screen.getAllByText('04/11/2026').length).toBeGreaterThan(0);
  });
});
