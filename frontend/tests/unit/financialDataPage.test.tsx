import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, expect, test, vi } from 'vitest';

import { FinancialDataPage } from '../../src/pages/FinancialDataPage';
import { clearSession, setSession } from '../../src/services/api';

const householdService = vi.hoisted(() => ({
  listHouseholds: vi.fn(), getDefaultHousehold: vi.fn(), createHousehold: vi.fn(), listMembers: vi.fn(),
  updateMemberRole: vi.fn(), removeMember: vi.fn(), leaveHousehold: vi.fn(), setDefaultHousehold: vi.fn(),
  listHouseholdInvitations: vi.fn(), listIncomingInvitations: vi.fn(), createInvitation: vi.fn(),
  cancelInvitation: vi.fn(), acceptInvitation: vi.fn(), declineInvitation: vi.fn(),
}));
const financialStateService = vi.hoisted(() => ({
  listHouseholdIncomes: vi.fn(), listHouseholdExpenses: vi.fn(), listHouseholdLiabilities: vi.fn(),
  listHouseholdAssets: vi.fn(), listHouseholdGoals: vi.fn(), createIncome: vi.fn(), createExpense: vi.fn(),
  createLiability: vi.fn(), createAsset: vi.fn(), createGoal: vi.fn(), updateIncome: vi.fn(),
  updateExpense: vi.fn(), updateLiability: vi.fn(), updateAsset: vi.fn(), updateGoal: vi.fn(),
  deleteIncome: vi.fn(), deleteExpense: vi.fn(), deleteLiability: vi.fn(), deleteAsset: vi.fn(), deleteGoal: vi.fn(),
}));
const financialService = vi.hoisted(() => ({
  getProfile: vi.fn(), upsertProfile: vi.fn(), getDiagnosis: vi.fn(), listIncomes: vi.fn(), listExpenses: vi.fn(),
  createIncome: vi.fn(), createExpense: vi.fn(),
}));
const authService = vi.hoisted(() => ({
  getMe: vi.fn(), login: vi.fn(), register: vi.fn(), logout: vi.fn(),
}));

vi.mock('../../src/features/household/services/household.service', () => householdService);
vi.mock('../../src/features/financial-state/services/financialState.service', () => financialStateService);
vi.mock('../../src/features/financial/services/financial.service', () => financialService);
vi.mock('../../src/features/auth/services/auth.service', () => authService);

const personal = { id: 1, name: 'Meu espaço', household_type: 'PERSONAL' as const, created_by_user_id: 10, status: 'ACTIVE' as const, created_at: '2026-10-06T12:00:00Z', updated_at: '2026-10-06T12:00:00Z' };
const shared = { ...personal, id: 2, name: 'Casa Medrado', household_type: 'SHARED' as const };
const income = { id: 101, household_id: 1, user_id: 10, ownership_scope: 'PERSONAL' as const, description: 'Salário', amount: '5000.00', income_type: 'salario', received_at: '2026-10-06', is_recurring: true, created_at: '2026-10-06T12:00:00Z', updated_at: '2026-10-06T12:00:00Z' };

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(<QueryClientProvider client={client}><FinancialDataPage /></QueryClientProvider>);
}

beforeEach(() => {
  clearSession();
  setSession('test-token', { id: 10, email: 'owner@example.com' });
  householdService.listHouseholds.mockResolvedValue([personal, shared]);
  householdService.getDefaultHousehold.mockResolvedValue(personal);
  householdService.listMembers.mockResolvedValue([{
    id: 11, household_id: 1, user_id: 10, role: 'OWNER', status: 'ACTIVE', is_default: true,
    joined_at: '2026-10-06T12:00:00Z', updated_at: '2026-10-06T12:00:00Z',
    email: 'owner@example.com', full_name: 'Owner',
  }]);
  authService.getMe.mockResolvedValue({ id: 10, email: 'owner@example.com', full_name: 'Owner', is_active: true });
  financialStateService.listHouseholdIncomes.mockResolvedValue([income]);
  financialStateService.listHouseholdExpenses.mockResolvedValue([]);
  financialStateService.listHouseholdLiabilities.mockResolvedValue([]);
  financialStateService.listHouseholdAssets.mockResolvedValue([]);
  financialStateService.listHouseholdGoals.mockResolvedValue([]);
  financialStateService.updateIncome.mockResolvedValue({ ...income, description: 'Salário principal' });
  financialStateService.createLiability.mockResolvedValue({ id: 201 });
  financialStateService.deleteGoal.mockResolvedValue(undefined);
  financialService.getProfile.mockResolvedValue({ id: 1, user_id: 10, monthly_salary: '5000.00', emergency_reserve: '1000.00', has_debt_default: false, risk_profile: 'moderate', investment_horizon_months: 120, created_at: '', updated_at: '' });
  financialService.upsertProfile.mockResolvedValue({});
});

test('edits an existing income through the canonical household endpoint', async () => {
  const user = userEvent.setup();
  renderPage();
  expect(await screen.findByText('Salário')).toBeInTheDocument();
  const incomesCard = screen.getByText('Receitas').closest('section');
  expect(incomesCard).not.toBeNull();
  await user.click(within(incomesCard as HTMLElement).getByRole('button', { name: 'Editar' }));
  const description = screen.getByLabelText('Descrição');
  await user.clear(description);
  await user.type(description, 'Salário principal');
  await user.click(screen.getByRole('button', { name: 'Salvar' }));
  await waitFor(() => expect(financialStateService.updateIncome).toHaveBeenCalledWith(1, 101, expect.objectContaining({
    ownership_scope: 'PERSONAL',
    description: 'Salário principal',
    amount: 5000,
  })));
});

test('preserves explicit zero and missing debt values as different inputs', async () => {
  const user = userEvent.setup();
  renderPage();
  const debtsCard = (await screen.findByText('Dívidas')).closest('section');
  await user.click(within(debtsCard as HTMLElement).getByRole('button', { name: 'Adicionar' }));
  await user.type(screen.getByLabelText('Nome'), 'Cartão');
  await user.type(screen.getByLabelText('Tipo de dívida'), 'credit_card');
  await user.type(screen.getByLabelText('Saldo atual (opcional)'), '0');
  await user.click(screen.getByRole('button', { name: 'Salvar' }));
  await waitFor(() => expect(financialStateService.createLiability).toHaveBeenCalledWith(1, expect.objectContaining({
    ownership_scope: 'PERSONAL',
    current_balance: 0,
    monthly_payment: null,
    annual_interest_rate_pct: null,
    due_date: null,
  })));
});

test('does not move a dirty goal draft when switching households', async () => {
  const user = userEvent.setup();
  renderPage();
  const goalsCard = (await screen.findByText('Objetivos')).closest('section');
  await user.click(within(goalsCard as HTMLElement).getByRole('button', { name: 'Adicionar' }));
  await user.type(screen.getByLabelText('Nome'), 'Viagem');
  await user.selectOptions(screen.getByLabelText('Casa'), '2');
  expect(await screen.findByRole('dialog', { name: 'Alterações não salvas' })).toBeInTheDocument();
  expect(screen.getByLabelText('Casa')).toHaveValue('1');
  await user.click(screen.getByRole('button', { name: 'Descartar e trocar' }));
  expect(screen.getByLabelText('Casa')).toHaveValue('2');
  expect(screen.queryByRole('dialog', { name: 'Adicionar objetivo' })).not.toBeInTheDocument();
});

test('edits the personal financial profile without attaching a household id', async () => {
  const user = userEvent.setup();
  renderPage();
  await user.click(await screen.findByRole('button', { name: 'Editar perfil' }));
  const reserve = screen.getByLabelText('Reserva de emergência atual');
  await user.clear(reserve);
  await user.type(reserve, '2500');
  const horizon = screen.getByRole('spinbutton', { name: /Horizonte de investimento/i });
  await user.clear(horizon);
  await user.type(horizon, '60');
  await user.click(screen.getByRole('button', { name: 'Salvar perfil' }));
  await waitFor(() => expect(financialService.upsertProfile).toHaveBeenCalledWith(expect.objectContaining({
    monthly_salary: 5000,
    emergency_reserve: 2500,
    investment_horizon_months: 60,
  })));
  expect(financialService.upsertProfile.mock.calls[0][0]).not.toHaveProperty('household_id');
});

test('preserves an unknown investment horizon as null', async () => {
  financialService.getProfile.mockResolvedValue({
    id: 1,
    user_id: 10,
    monthly_salary: '5000.00',
    emergency_reserve: '1000.00',
    has_debt_default: false,
    risk_profile: 'moderate',
    investment_horizon_months: null,
    created_at: '',
    updated_at: '',
  });
  const user = userEvent.setup();
  renderPage();
  expect((await screen.findAllByText('Não informado')).length).toBeGreaterThan(0);
  await user.click(screen.getByRole('button', { name: 'Editar perfil' }));
  await user.click(screen.getByRole('button', { name: 'Salvar perfil' }));

  await waitFor(() => expect(financialService.upsertProfile).toHaveBeenCalledWith(
    expect.objectContaining({ investment_horizon_months: null }),
  ));
});
