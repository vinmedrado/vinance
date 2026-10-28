import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, test, vi } from 'vitest';
import { TradingPage } from '../../src/pages/TradingPage';

const state = vi.hoisted(() => ({
  active: 'overview',
  createAccount: vi.fn(),
  createOrder: vi.fn(),
  cancelOrder: vi.fn(),
  closePosition: vi.fn(),
}));

const success = <T,>(data: T) => ({ data, isLoading: false, error: null });
const mutation = (mutate: (...args: unknown[]) => unknown) => ({ mutate, isPending: false });

vi.mock('../../src/features/household/hooks/useHousehold', () => ({
  useHouseholdDefault: () => success({ id: 7, name: 'Casa pessoal' }),
  useHouseholdList: () => success([{ id: 7, name: 'Casa pessoal' }]),
}));

vi.mock('../../src/features/trading/hooks/useTrading', () => ({
  useTradingOverview: () => success({
    paper_only: true,
    product_status: 'NOT_PAPER_READY',
    risk_budget: {
      paper_only: true,
      real_trading_allowed: false,
      real_trading_capital: '0',
      paper_simulation_allowed: true,
      financial_status: 'BLOCKED',
      risk_budget_status: 'DATA_BLOCKED',
      protected_capital: null,
      speculative_capital: '0',
      blocking_reasons: ['REAL_TRADING_NOT_SUPPORTED'],
      context_fingerprints: {},
      household_id: 7,
      simulation_rules: {},
    },
    paper_account: null,
    counts: {},
    performance: {},
    models: { status: 'NOT_PAPER_READY', paper_trading_ready: false },
  }),
  useTradingOpportunities: () => success({ items: [], total: 0, limit: 50, offset: 0 }),
  usePaperOrders: () => success({ items: [], total: 0, limit: 50, offset: 0 }),
  usePaperPositions: () => success({ items: [], total: 0, limit: 50, offset: 0 }),
  usePaperEvents: () => success({ items: [], total: 0, limit: 100, offset: 0 }),
  useTradingBacktests: () => success({ items: [], total: 0, limit: 50, offset: 0 }),
  useTradingModels: () => success({ items: [], total: 0, limit: 100, offset: 0 }),
  useTradingMutations: () => ({
    createAccount: mutation(state.createAccount),
    createOrder: mutation(state.createOrder),
    cancelOrder: mutation(state.cancelOrder),
    closePosition: mutation(state.closePosition),
  }),
}));

beforeEach(() => {
  state.createAccount.mockClear();
  state.createOrder.mockClear();
});

describe('Trading Assistido', () => {
  test('identifica permanentemente a simulação e bloqueia Trading real', () => {
    render(<TradingPage />);
    expect(screen.getByRole('heading', { name: 'Trading' })).toBeInTheDocument();
    expect(screen.getAllByText(/nenhuma ordem real/i).length).toBeGreaterThan(0);
    expect(screen.getByText('PAPER ONLY')).toBeInTheDocument();
    expect(screen.getByText('Trading real')).toBeInTheDocument();
    expect(screen.getByText('R$ 0,00')).toBeInTheDocument();
    expect(screen.getByText('Disponível para simulação')).toBeInTheDocument();
    expect(screen.getByText('Nenhum modelo aprovado para oportunidades Paper neste momento.')).toBeInTheDocument();
  });

  test('explica o saldo virtual antes de criar uma conta pessoal', async () => {
    render(<TradingPage />);
    expect(screen.getByText(/10.000 USDT virtuais/i)).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Criar conta Paper' }));
    expect(state.createAccount).toHaveBeenCalledOnce();
  });

  test('não fabrica oportunidade quando não existe modelo validado', async () => {
    render(<TradingPage />);
    await userEvent.click(screen.getByRole('tab', { name: 'Oportunidades' }));
    expect(screen.getByText('Nenhuma oportunidade validada neste momento')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Simular compra' })).not.toBeInTheDocument();
  });
});
