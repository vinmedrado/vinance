import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, expect, test, vi } from 'vitest';

import { FinancialPage } from '../../src/pages/FinancialPage';
import type { FinancialState, Household } from '../../src/features/financial-state/types/financialState.types';


const service = vi.hoisted(() => ({
  listHouseholds: vi.fn(),
  getDefaultHousehold: vi.fn(),
  getCurrentFinancialState: vi.fn(),
  createFinancialStateSnapshot: vi.fn(),
  getFinancialStateHistory: vi.fn(),
  listHouseholdIncomes: vi.fn(),
  listHouseholdExpenses: vi.fn(),
  createIncome: vi.fn(),
  createExpense: vi.fn(),
}));

const financialHooks = vi.hoisted(() => ({ useFinancialProfile: vi.fn() }));

vi.mock('../../src/features/financial-state/services/financialState.service', () => service);
vi.mock('../../src/features/financial/hooks/useFinancial', () => financialHooks);

const household: Household = {
  id: 10,
  name: 'Casa de Ana',
  household_type: 'PERSONAL',
  created_by_user_id: 1,
  status: 'ACTIVE',
  created_at: '2026-09-08T12:00:00Z',
  updated_at: '2026-09-08T12:00:00Z',
};

const state: FinancialState = {
  household_id: 10,
  engine_version: 'household-financial-state-v1',
  evaluated_at: '2026-09-08T12:00:00Z',
  metrics: {
    recurring_monthly_income: '5000.00',
    non_recurring_income: null,
    total_income: null,
    fixed_expenses: '1000.00',
    variable_expenses: null,
    total_expenses: '1000.00',
    cash_flow: '123.45',
    disposable_income: '4000.00',
    savings_capacity: '4000.00',
    investment_capacity: '4000.00',
    total_assets: '10000.00',
    total_liabilities: '0.00',
    net_worth: '10000.00',
    emergency_reserve: '3000.00',
    emergency_reserve_months: '3.00',
    monthly_debt_service: '0.00',
    debt_to_income: '0.00',
    debt_service_ratio: '0.00',
    savings_rate: '80.00',
    asset_distribution: { CASH: { amount: '10000.00', percentage: '100.00' } },
  },
  goals: [],
  member_views: [{
    user_id: 1,
    full_name: 'Ana',
    metrics: {} as FinancialState['metrics'],
    goals: [],
    missing_fields: [],
    inconsistencies: [],
    provenance: {},
  }],
  data_quality: 'PARTIAL',
  confidence: 82,
  missing_fields: ['income.non_recurring', 'expenses.variable'],
  inconsistencies: [],
  stale_fields: [],
  provenance: {},
};

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } });
  return render(<QueryClientProvider client={client}><FinancialPage /></QueryClientProvider>);
}

beforeEach(() => {
  service.listHouseholds.mockReset().mockResolvedValue([household]);
  service.getDefaultHousehold.mockReset().mockResolvedValue(household);
  service.getCurrentFinancialState.mockReset().mockResolvedValue(state);
  service.getFinancialStateHistory.mockReset().mockResolvedValue({ items: [], total: 0 });
  service.createFinancialStateSnapshot.mockReset().mockResolvedValue({ id: 1 });
  service.listHouseholdIncomes.mockReset().mockResolvedValue([]);
  service.listHouseholdExpenses.mockReset().mockResolvedValue([]);
  service.createIncome.mockReset().mockResolvedValue({ id: 1 });
  service.createExpense.mockReset().mockResolvedValue({ id: 1 });
  financialHooks.useFinancialProfile.mockReset().mockReturnValue({ data: { id: 1 }, error: null, refetch: vi.fn() });
  vi.stubGlobal('crypto', { randomUUID: () => '00000000-0000-4000-8000-000000000001' });
});

test('usa métricas do engine e distingue ausência de zero real', async () => {
  renderPage();

  expect(await screen.findByRole('heading', { name: 'Minha situação financeira' })).toBeInTheDocument();
  expect(await screen.findByText('Parcial · 82%')).toBeInTheDocument();
  expect(screen.getByText(/123,45/)).toBeInTheDocument();
  expect(screen.getByText(/Variáveis: Não informado/)).toBeInTheDocument();
  expect(screen.getByText(/Dívidas:.*0,00/)).toBeInTheDocument();
  expect(screen.getByText('Renda não recorrente deste mês')).toBeInTheDocument();
  expect(screen.getByText('Despesas variáveis deste mês')).toBeInTheDocument();
});

test('salva snapshot auditável pelo endpoint dedicado', async () => {
  renderPage();

  await userEvent.click(await screen.findByRole('button', { name: 'Salvar retrato' }));
  expect(service.createFinancialStateSnapshot).toHaveBeenCalledWith(
    10,
    'financial-state-10-00000000-0000-4000-8000-000000000001',
  );
  expect(await screen.findByText('Retrato financeiro salvo no histórico.')).toBeInTheDocument();
});

test('mantém o cadastro de receita e envia ownership explícito ao household selecionado', async () => {
  const user = userEvent.setup();
  renderPage();

  await screen.findByRole('heading', { name: 'Minha situação financeira' });
  await user.click(await screen.findByRole('button', { name: 'Nova receita' }));
  await user.type(screen.getByLabelText('Descrição'), 'Salário');
  await user.type(screen.getByLabelText('Valor'), '5000');
  await user.click(screen.getByRole('button', { name: 'Salvar receita' }));

  await waitFor(() => expect(service.createIncome).toHaveBeenCalledWith(10, expect.objectContaining({
    amount: 5000,
    description: 'Salário',
    ownership_scope: 'PERSONAL',
  })));
});
