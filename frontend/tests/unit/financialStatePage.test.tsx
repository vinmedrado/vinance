import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, expect, test, vi } from 'vitest';

import { FinancialPage } from '../../src/pages/FinancialPage';
import {
  capitalAllocationQueryKey,
  financialPolicyQueryKey,
  financialStateQueryKey,
} from '../../src/features/financial-state/hooks/useFinancialState';
import type {
  CapitalAllocation,
  FinancialPolicy,
  FinancialState,
  Household,
} from '../../src/features/financial-state/types/financialState.types';
import { clearSession, setSession } from '../../src/services/api';


const service = vi.hoisted(() => ({
  listHouseholds: vi.fn(),
  getDefaultHousehold: vi.fn(),
  getCurrentFinancialState: vi.fn(),
  getCurrentFinancialPolicy: vi.fn(),
  createFinancialPolicyDecision: vi.fn(),
  getFinancialPolicyHistory: vi.fn(),
  getFinancialPolicyDecision: vi.fn(),
  getCurrentCapitalAllocation: vi.fn(),
  getCapitalAllocationFromPolicy: vi.fn(),
  createCapitalAllocationDecision: vi.fn(),
  getCapitalAllocationHistory: vi.fn(),
  getCapitalAllocationDecision: vi.fn(),
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

const secondHousehold: Household = {
  ...household,
  id: 20,
  name: 'Casa de Bia',
  household_type: 'SHARED',
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

const policy: FinancialPolicy = {
  policy_id: null,
  household_id: 10,
  financial_state_snapshot_id: null,
  engine_version: 'financial-policy-v1',
  rules_version: 'financial-policy-rules-v1',
  evaluated_at: '2026-09-08T12:00:00Z',
  generated_at: '2026-09-08T12:00:00Z',
  created_at: null,
  input_fingerprint: 'a'.repeat(64),
  ruleset_fingerprint: 'b'.repeat(64),
  decision_fingerprint: 'c'.repeat(64),
  policy_state: 'EMERGENCY_RESERVE_PRIORITY',
  investment_readiness: 'LIMITED',
  summary: 'A prioridade atual é fortalecer a reserva de emergência.',
  priority_stack: [
    {
      rank: 1,
      code: 'BUILD_EMERGENCY_RESERVE',
      title: 'Fortalecer a reserva de emergência',
      explanation: 'Aproxime a reserva do alvo dinâmico calculado com o contexto conhecido.',
      status: 'ACTIVE',
      evidence_refs: ['EMERGENCY_RESERVE'],
    },
    {
      rank: 2,
      code: 'INVEST_SURPLUS_CAPITAL',
      title: 'Investir somente o capital excedente',
      explanation: 'Ativos, mercados e quantidades não são escolhidos aqui.',
      status: 'CONDITIONAL',
      evidence_refs: ['INVESTMENT_CAPACITY'],
    },
  ],
  data_gate: {
    status: 'LIMITED',
    critical_missing_fields: [],
    readiness_missing_fields: [],
    critical_stale_fields: [],
    currencies: ['BRL'],
    missing_currency_fields: [],
    readiness_limiters: ['SOURCE_QUALITY_NOT_COMPLETE'],
  },
  debt_policy: {},
  reserve_policy: {},
  goal_policy: {},
  blockers: [],
  warnings: [{
    code: 'STALE_DATA_PRESENT',
    message: 'Confirme os dados antes de ampliar novos aportes.',
    fields: [],
    rule_ids: [],
  }],
  limitations: [],
  missing_information: [],
  explanations: [
    {
      code: 'PRIMARY_POLICY_DECISION',
      decision: 'Fortalecer a reserva de emergência',
      reason: 'Sua reserva atual cobre 3 meses e ainda está abaixo do alvo vigente.',
      evidence_refs: ['EMERGENCY_RESERVE'],
      rule_ids: ['FPV1-RESERVE-002'],
      blocked_alternatives: ['INVEST_SURPLUS_CAPITAL'],
    },
    {
      code: 'INVESTMENT_READINESS_DECISION',
      decision: 'LIMITED',
      reason: 'Novos investimentos permanecem limitados pela prioridade atual.',
      evidence_refs: ['INVESTMENT_CAPACITY'],
      rule_ids: ['FPV1-READY-001'],
      blocked_alternatives: ['FULL_NEW_INVESTMENT'],
    },
  ],
  evidence: [
    {
      code: 'EMERGENCY_RESERVE',
      label: 'Reserva de emergência',
      value: '3000.00',
      unit: 'BRL',
      source: 'financial_state.metrics.emergency_reserve',
    },
  ],
  member_policy_views: [],
  rules_evaluated: [],
  ruleset: {},
  source_financial_state: {},
  previous_financial_state: {},
};

const allocation: CapitalAllocation = {
  allocation_id: null,
  household_id: 10,
  financial_state_snapshot_id: null,
  financial_policy_id: null,
  engine_version: 'capital-allocation-v1',
  rules_version: 'capital-allocation-rules-v1',
  allocation_period: 'MONTHLY',
  allocation_status: 'SURPLUS',
  currency: 'BRL',
  allocatable_capital: '4000.00',
  allocated_capital: '4000.00',
  remaining_capital: '0.00',
  investment_bucket_amount: '1000.00',
  bucket_totals: {
    protected_capital: '3000.00',
    goal_capital: '0.00',
    investment_capital: '1000.00',
    speculative_capital: '0.00',
  },
  allocations: [
    {
      priority_code: 'BUILD_EMERGENCY_RESERVE',
      priority_rank: 1,
      bucket_type: 'PROTECTED_CAPITAL',
      target_type: 'EMERGENCY_RESERVE',
      target_id: null,
      target_name: 'Reserva de emergência',
      ownership_scope: 'HOUSEHOLD',
      user_id: null,
      requested_amount: '3000.00',
      allocated_amount: '3000.00',
      remaining_need: '0.00',
      status: 'FUNDED',
      reason: 'O gap veio da política financeira vigente.',
      evidence_refs: ['EMERGENCY_RESERVE'],
    },
    {
      priority_code: 'INVEST_SURPLUS_CAPITAL',
      priority_rank: 2,
      bucket_type: 'INVESTMENT_CAPITAL',
      target_type: 'INVESTMENT',
      target_id: null,
      target_name: 'Capital elegível para investimentos',
      ownership_scope: null,
      user_id: null,
      requested_amount: '1000.00',
      allocated_amount: '1000.00',
      remaining_need: '0.00',
      status: 'ALLOCATED',
      reason: 'Residual permitido pela política.',
      evidence_refs: ['INVESTMENT_CAPACITY'],
    },
  ],
  unfunded_priorities: [],
  member_impacts: [],
  blockers: [],
  warnings: [],
  missing_information: [],
  evidence: [],
  rules_evaluated: [],
  data_gate: {
    status: 'PASS',
    state_quality: 'COMPLETE',
    state_confidence: 100,
    policy_state: 'INVESTMENT_READY',
    investment_readiness: 'READY',
    currencies: ['BRL'],
    critical_stale_fields: [],
    consistency_checks: { capital_conservation: true },
  },
  ruleset: {},
  source_financial_state: {},
  source_financial_policy: {},
  input_fingerprint: 'd'.repeat(64),
  policy_fingerprint: 'c'.repeat(64),
  ruleset_fingerprint: 'e'.repeat(64),
  decision_fingerprint: 'f'.repeat(64),
  generated_at: '2026-09-08T12:00:00Z',
  created_at: null,
};

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } });
  return {
    client,
    ...render(<QueryClientProvider client={client}><FinancialPage /></QueryClientProvider>),
  };
}

beforeEach(() => {
  clearSession('logout');
  service.listHouseholds.mockReset().mockResolvedValue([household]);
  service.getDefaultHousehold.mockReset().mockResolvedValue(household);
  service.getCurrentFinancialState.mockReset().mockResolvedValue(state);
  service.getCurrentFinancialPolicy.mockReset().mockResolvedValue(policy);
  service.getFinancialPolicyHistory.mockReset().mockResolvedValue({ items: [], total: 0 });
  service.getFinancialPolicyDecision.mockReset().mockResolvedValue(policy);
  service.getCurrentCapitalAllocation.mockReset().mockResolvedValue(allocation);
  service.getCapitalAllocationFromPolicy.mockReset().mockResolvedValue(allocation);
  service.getCapitalAllocationHistory.mockReset().mockResolvedValue({ items: [], total: 0 });
  service.getCapitalAllocationDecision.mockReset().mockResolvedValue(allocation);
  service.createCapitalAllocationDecision.mockReset().mockResolvedValue({
    ...allocation,
    allocation_id: 23,
    financial_state_snapshot_id: 7,
    financial_policy_id: 17,
    created_at: '2026-09-08T12:00:01Z',
  });
  service.createFinancialPolicyDecision.mockReset().mockResolvedValue({
    ...policy,
    policy_id: 17,
    financial_state_snapshot_id: 7,
    created_at: '2026-09-08T12:00:01Z',
  });
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
  expect(await screen.findByRole('heading', { name: 'Sua prioridade agora' })).toBeInTheDocument();
  expect(await screen.findByRole('heading', { name: 'Plano deste período' })).toBeInTheDocument();
  expect(screen.getByText('COM CAPITAL ELEGÍVEL')).toHaveClass('vn-badge--success');
  expect(screen.getByRole('heading', { name: /R\$\s*4\.000,00/ })).toBeInTheDocument();
  expect(screen.getByText('Capital elegível para investimentos')).toBeInTheDocument();
  expect(screen.getByText('LIMITADO')).toHaveClass('vn-badge--warning');
  expect(screen.getByRole('heading', { name: 'Fortalecer a reserva de emergência' })).toBeInTheDocument();
  expect(screen.getByText('Sua reserva atual cobre 3 meses e ainda está abaixo do alvo vigente.')).toBeInTheDocument();
  expect(screen.getByText(/Investir somente o capital excedente/)).toBeInTheDocument();
  expect(screen.getByText(/123,45/)).toBeInTheDocument();
  expect(screen.getByText(/Variáveis: Não informado/)).toBeInTheDocument();
  expect(screen.getByText(/Dívidas:.*0,00/)).toBeInTheDocument();
  expect(screen.getByText('Renda não recorrente deste mês')).toBeInTheDocument();
  expect(screen.getByText('Despesas variáveis deste mês')).toBeInTheDocument();
});

test('não reutiliza dados financeiros quando a identidade da sessão muda', async () => {
  setSession('session-token-a', { id: 1 });
  renderPage();

  await waitFor(() => expect(service.getCurrentFinancialPolicy).toHaveBeenCalledTimes(1));
  act(() => setSession('session-token-b', { id: 2 }));

  await waitFor(() => expect(service.getCurrentFinancialPolicy).toHaveBeenCalledTimes(2));
  expect(service.getCurrentFinancialState).toHaveBeenCalledTimes(2);
  expect(service.getCurrentCapitalAllocation).toHaveBeenCalledTimes(2);
  expect(service.listHouseholds).toHaveBeenCalledTimes(2);
});

test('isola falha da política sem esconder o Financial State', async () => {
  service.getCurrentFinancialPolicy.mockRejectedValueOnce(new Error('Política indisponível'));

  renderPage();

  expect(await screen.findByText('Política indisponível')).toBeInTheDocument();
  expect(screen.getByText(/123,45/)).toBeInTheDocument();
  expect(screen.queryByText('Não foi possível carregar sua situação')).not.toBeInTheDocument();
});

test('isola falha do plano sem esconder State nem Policy', async () => {
  service.getCurrentCapitalAllocation.mockRejectedValueOnce(new Error('Plano indisponível'));

  renderPage();

  expect(await screen.findByText('Plano indisponível')).toBeInTheDocument();
  expect(screen.getByText(/123,45/)).toBeInTheDocument();
  expect(screen.getByRole('heading', { name: 'Sua prioridade agora' })).toBeInTheDocument();
});

test('mostra capital desconhecido sem convertê-lo em zero', async () => {
  service.getCurrentCapitalAllocation.mockResolvedValueOnce({
    ...allocation,
    allocation_status: 'BLOCKED',
    allocatable_capital: null,
    allocated_capital: '0.00',
    remaining_capital: null,
    investment_bucket_amount: '0.00',
    allocations: [],
    blockers: [{ code: 'DATA', message: 'Informe renda e despesas.', fields: [], rule_ids: [] }],
  });

  renderPage();

  expect((await screen.findAllByText('Não calculável')).length).toBeGreaterThanOrEqual(1);
  expect(screen.getByText('Os dados atuais não permitem afirmar quanto pode ser distribuído.')).toBeInTheDocument();
  expect(screen.getByText('Informe renda e despesas.')).toBeInTheDocument();
});

test('não apresenta histórico vazio quando a consulta de decisões falha', async () => {
  service.getFinancialPolicyHistory.mockRejectedValueOnce(new Error('Histórico indisponível'));

  renderPage();

  expect(await screen.findByText('Histórico indisponível')).toBeInTheDocument();
  expect(screen.queryByText('Nenhuma decisão foi congelada ainda.')).not.toBeInTheDocument();
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

test('congela decisão auditável e atualiza o histórico sem lógica financeira no cliente', async () => {
  renderPage();

  await userEvent.click(await screen.findByRole('button', { name: 'Salvar decisão' }));

  expect(service.createFinancialPolicyDecision).toHaveBeenCalledWith(
    10,
    'financial-policy-10-00000000-0000-4000-8000-000000000001',
  );
  expect(await screen.findByText('Decisão financeira salva no histórico.')).toBeInTheDocument();
});

test('congela o plano completo com chave idempotente própria', async () => {
  renderPage();

  await userEvent.click(await screen.findByRole('button', { name: 'Salvar plano' }));

  expect(service.createCapitalAllocationDecision).toHaveBeenCalledWith(
    10,
    'capital-allocation-10-00000000-0000-4000-8000-000000000001',
  );
  expect(await screen.findByText('Plano de capital salvo no histórico.')).toBeInTheDocument();
});

test('mantém o plano congelado no cache do household que iniciou o POST', async () => {
  service.listHouseholds.mockResolvedValueOnce([household, secondHousehold]);
  let resolveAllocation!: (decision: CapitalAllocation) => void;
  service.createCapitalAllocationDecision.mockReturnValueOnce(
    new Promise<CapitalAllocation>((resolve) => { resolveAllocation = resolve; }),
  );
  const { client } = renderPage();
  const setQueryData = vi.spyOn(client, 'setQueryData');
  const invalidateQueries = vi.spyOn(client, 'invalidateQueries');

  await userEvent.click(await screen.findByRole('button', { name: 'Salvar plano' }));
  await userEvent.selectOptions(screen.getByLabelText('Household'), '20');
  act(() => resolveAllocation({
    ...allocation,
    allocation_id: 23,
    household_id: 10,
    financial_state_snapshot_id: 7,
    financial_policy_id: 17,
    created_at: '2026-09-08T12:00:01Z',
  }));

  expect(await screen.findByText('Plano de capital salvo no histórico.')).toBeInTheDocument();
  expect(setQueryData).toHaveBeenCalledWith(
    capitalAllocationQueryKey(null, 'history', 10, 23),
    expect.objectContaining({ allocation_id: 23, household_id: 10 }),
  );
  expect(setQueryData).not.toHaveBeenCalledWith(
    capitalAllocationQueryKey(null, 'history', 20, 23),
    expect.anything(),
  );
  expect(invalidateQueries).toHaveBeenCalledWith({
    queryKey: financialPolicyQueryKey(null, 'current', 10),
  });
  expect(invalidateQueries).toHaveBeenCalledWith({
    queryKey: financialStateQueryKey(null, 'current', 10),
  });
});

test('mantém a resposta da decisão no cache do household que iniciou o POST', async () => {
  service.listHouseholds.mockResolvedValueOnce([household, secondHousehold]);
  let resolveDecision!: (decision: FinancialPolicy) => void;
  service.createFinancialPolicyDecision.mockReturnValueOnce(
    new Promise<FinancialPolicy>((resolve) => { resolveDecision = resolve; }),
  );
  const { client } = renderPage();
  const setQueryData = vi.spyOn(client, 'setQueryData');

  await userEvent.click(await screen.findByRole('button', { name: 'Salvar decisão' }));
  await waitFor(() => expect(service.createFinancialPolicyDecision).toHaveBeenCalledWith(
    10,
    'financial-policy-10-00000000-0000-4000-8000-000000000001',
  ));
  await userEvent.selectOptions(screen.getByLabelText('Household'), '20');
  act(() => resolveDecision({
    ...policy,
    policy_id: 17,
    household_id: 10,
    financial_state_snapshot_id: 7,
    created_at: '2026-09-08T12:00:01Z',
  }));

  expect(await screen.findByText('Decisão financeira salva no histórico.')).toBeInTheDocument();
  expect(setQueryData).toHaveBeenCalledWith(
    financialPolicyQueryKey(null, 'history', 10, 17),
    expect.objectContaining({ policy_id: 17, household_id: 10 }),
  );
  expect(setQueryData).not.toHaveBeenCalledWith(
    financialPolicyQueryKey(null, 'history', 20, 17),
    expect.anything(),
  );
});

test('mostra visões pessoais distintas quando o backend retorna um casal', async () => {
  service.getCurrentFinancialPolicy.mockResolvedValueOnce({
    ...policy,
    member_policy_views: [
      {
        user_id: 1,
        full_name: 'Ana',
        scope: 'PERSONAL_ONLY',
        policy_state: 'BALANCED_BUILD',
        investment_readiness: 'LIMITED',
        priority_signals: ['COMPLETE_READINESS_DATA'],
        metrics: {},
        goals: [],
        missing_information: [],
        inconsistencies: [],
        explanation: 'Visão pessoal de Ana.',
      },
      {
        user_id: 2,
        full_name: 'Bia',
        scope: 'PERSONAL_ONLY',
        policy_state: 'CASHFLOW_RECOVERY',
        investment_readiness: 'BLOCKED',
        priority_signals: ['STABILIZE_CASH_FLOW'],
        metrics: {},
        goals: [],
        missing_information: [],
        inconsistencies: [],
        explanation: 'Visão pessoal de Bia.',
      },
    ],
  });

  renderPage();

  expect(await screen.findByRole('heading', { name: 'Visões individuais' })).toBeInTheDocument();
  expect(screen.getByText('Ana')).toBeInTheDocument();
  expect(screen.getByText('Bia')).toBeInTheDocument();
  expect(screen.getByText(/Visão pessoal de Bia/)).toBeInTheDocument();
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
