import { expect, test, type Page, type Route } from '@playwright/test';

import { authenticatedUser, fakeAccessToken } from '../fixtures/investmentFixtures';

const apiHeaders = {
  'access-control-allow-origin': 'http://127.0.0.1:4173',
  'access-control-allow-headers': 'authorization,content-type,idempotency-key',
  'access-control-allow-methods': 'GET,POST,PATCH,DELETE,OPTIONS',
};

async function json(route: Route, body: unknown, status = 200) {
  if (route.request().method() === 'OPTIONS') {
    await route.fulfill({ status: 204, headers: apiHeaders });
    return;
  }
  await route.fulfill({ status, headers: apiHeaders, contentType: 'application/json', body: JSON.stringify(body) });
}

async function seedSession(page: Page) {
  await page.goto('/login');
  await page.evaluate(({ accessToken, user }) => {
    window.localStorage.setItem('vinance_access_token', accessToken);
    window.localStorage.setItem('vinance_user', JSON.stringify(user));
  }, { accessToken: fakeAccessToken(), user: authenticatedUser });
}

const household = {
  id: 10,
  name: 'Casa de Ana e Beto',
  household_type: 'SHARED',
  created_by_user_id: 1,
  status: 'ACTIVE',
  created_at: '2026-09-08T12:00:00Z',
  updated_at: '2026-09-08T12:00:00Z',
};

const financialState = {
  household_id: 10,
  engine_version: 'household-financial-state-v1',
  evaluated_at: '2026-09-08T12:00:00Z',
  metrics: {
    recurring_monthly_income: '5000.00', non_recurring_income: null, total_income: null,
    fixed_expenses: '1000.00', variable_expenses: null, total_expenses: '1000.00',
    cash_flow: null, disposable_income: '4000.00', savings_capacity: '4000.00',
    investment_capacity: '4000.00', total_assets: '10000.00', total_liabilities: '0.00',
    net_worth: '10000.00', emergency_reserve: '3000.00', emergency_reserve_months: '3.00',
    monthly_debt_service: '0.00', debt_to_income: '0.00', debt_service_ratio: '0.00',
    savings_rate: '80.00', asset_distribution: { CASH: { amount: '10000.00', percentage: '100.00' } },
  },
  goals: [],
  member_views: [{
    user_id: 1, full_name: 'Ana', metrics: {}, goals: [], missing_fields: [], inconsistencies: [], provenance: {},
  }],
  data_quality: 'PARTIAL',
  confidence: 82,
  missing_fields: ['income.non_recurring', 'expenses.variable'],
  inconsistencies: [],
  stale_fields: [],
  provenance: {},
};

const financialPolicy = {
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
  data_gate: { status: 'LIMITED', critical_missing_fields: [], readiness_missing_fields: [] },
  debt_policy: {}, reserve_policy: {}, goal_policy: {}, blockers: [], warnings: [], limitations: [],
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
      code: 'EMERGENCY_RESERVE', label: 'Reserva de emergência', value: '3000.00', unit: 'BRL', source: 'state',
    },
  ],
  member_policy_views: [],
  rules_evaluated: [], ruleset: {}, source_financial_state: {}, previous_financial_state: {},
};

const capitalAllocation = {
  allocation_id: null,
  household_id: 10,
  financial_state_snapshot_id: null,
  financial_policy_id: null,
  engine_version: 'capital-allocation-v1',
  rules_version: 'capital-allocation-rules-v1',
  allocation_period: 'MONTHLY',
  allocation_status: 'CONSTRAINED',
  currency: 'BRL',
  allocatable_capital: '4000.00',
  allocated_capital: '3000.00',
  remaining_capital: '1000.00',
  investment_bucket_amount: '0.00',
  bucket_totals: {
    protected_capital: '3000.00', goal_capital: '0.00', investment_capital: '0.00', speculative_capital: '0.00',
  },
  allocations: [
    {
      priority_code: 'BUILD_EMERGENCY_RESERVE', priority_rank: 1, bucket_type: 'PROTECTED_CAPITAL',
      target_type: 'EMERGENCY_RESERVE', target_id: null, target_name: 'Reserva de emergência',
      ownership_scope: 'HOUSEHOLD', user_id: null, requested_amount: '5000.00',
      allocated_amount: '3000.00', remaining_need: '2000.00', status: 'PARTIALLY_FUNDED',
      reason: 'A reserva ainda está abaixo do alvo vigente.', evidence_refs: ['EMERGENCY_RESERVE'],
    },
    {
      priority_code: 'INVEST_SURPLUS_CAPITAL', priority_rank: 2, bucket_type: 'INVESTMENT_CAPITAL',
      target_type: 'INVESTMENT', target_id: null, target_name: 'Capital elegível para investimentos',
      ownership_scope: null, user_id: null, requested_amount: '0.00', allocated_amount: '0.00',
      remaining_need: '0.00', status: 'BLOCKED', reason: 'A prioridade superior ainda não foi atendida.',
      evidence_refs: ['INVESTMENT_READINESS'],
    },
  ],
  unfunded_priorities: [], member_impacts: [], blockers: [], warnings: [], missing_information: [],
  evidence: [], rules_evaluated: [], data_gate: {}, ruleset: {}, source_financial_state: {},
  source_financial_policy: {}, input_fingerprint: 'd'.repeat(64), policy_fingerprint: 'c'.repeat(64),
  ruleset_fingerprint: 'e'.repeat(64), decision_fingerprint: 'f'.repeat(64),
  generated_at: '2026-09-08T12:00:00Z', created_at: null,
};

const investmentOrchestration = {
  orchestration_id: null,
  household_id: 10,
  financial_state_snapshot_id: null,
  financial_policy_decision_id: null,
  capital_allocation_decision_id: null,
  engine_version: 'investment-orchestrator-v1',
  rules_version: 'investment-orchestrator-rules-v1',
  status: 'BLOCKED',
  currency: 'BRL',
  investment_budget: '0.00',
  profile_context: { status: 'COMPLETE', effective_profile: 'MODERATE' },
  portfolio_context: { status: 'UNKNOWN' },
  market_context: { status: 'NOT_CONSULTED' },
  asset_class_decisions: [],
  class_allocations: [],
  ranked_opportunities: [],
  suggested_capital: '0.00',
  remaining_investment_cash: '0.00',
  speculative_capital: '0.00',
  trading_dispatch: false,
  blockers: [{
    code: 'NO_AUTHORIZED_INVESTMENT_CAPITAL',
    message: 'Não há capital comprovadamente liberado para novos investimentos.',
    fields: ['capital_allocation.investment_bucket_amount'],
    rule_ids: ['IOV1-GATE-001'],
  }],
  warnings: [],
  missing_information: [],
  evidence: [],
  rule_traces: [],
  state_fingerprint: '1'.repeat(64), policy_fingerprint: '2'.repeat(64),
  allocation_fingerprint: '3'.repeat(64), market_context_fingerprint: '4'.repeat(64),
  ruleset_fingerprint: '5'.repeat(64), decision_fingerprint: '6'.repeat(64),
  generated_at: '2026-09-08T12:00:00Z', created_at: null,
};

test('financial state preserva ausência, ownership e idempotência de snapshot', async ({ page }) => {
  const incomePayloads: unknown[] = [];
  const snapshotKeys: string[] = [];
  const policyKeys: string[] = [];
  const allocationKeys: string[] = [];
  const orchestrationKeys: string[] = [];
  let snapshotAttempts = 0;
  let policyAttempts = 0;
  let allocationAttempts = 0;
  let orchestrationAttempts = 0;

  await page.route('**/api/v1/me', (route) => json(route, authenticatedUser));
  await page.route('**/api/v1/financial/**', async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    if (request.method() === 'OPTIONS') return json(route, null);
    if (path.endsWith('/financial/profile')) return json(route, { id: 1 });
    if (path.endsWith('/households/default')) return json(route, household);
    if (path.endsWith('/financial/households')) return json(route, [household]);
    if (path.endsWith('/households/10/investment-orchestration/history')) {
      return json(route, { items: [], total: 0 });
    }
    if (path.endsWith('/households/10/investment-orchestration/decisions')) {
      orchestrationAttempts += 1;
      orchestrationKeys.push(request.headers()['idempotency-key']);
      if (orchestrationAttempts === 1) return json(route, { detail: 'temporariamente indisponível' }, 503);
      return json(route, {
        ...investmentOrchestration,
        orchestration_id: 31,
        financial_state_snapshot_id: 7,
        financial_policy_decision_id: 17,
        capital_allocation_decision_id: 23,
        created_at: '2026-09-08T12:00:01Z',
      }, 201);
    }
    if (path.endsWith('/households/10/investment-orchestration')) return json(route, investmentOrchestration);
    if (path.endsWith('/households/10/capital-allocation/history')) {
      return json(route, { items: [], total: 0 });
    }
    if (path.endsWith('/households/10/capital-allocation/decisions')) {
      allocationAttempts += 1;
      allocationKeys.push(request.headers()['idempotency-key']);
      if (allocationAttempts === 1) return json(route, { detail: 'temporariamente indisponível' }, 503);
      return json(route, {
        ...capitalAllocation,
        allocation_id: 23,
        financial_state_snapshot_id: 7,
        financial_policy_id: 17,
        created_at: '2026-09-08T12:00:01Z',
      }, 201);
    }
    if (path.endsWith('/households/10/capital-allocation')) return json(route, capitalAllocation);
    if (path.endsWith('/households/10/financial-policy/history')) {
      return json(route, { items: [], total: 0 });
    }
    if (path.endsWith('/households/10/financial-policy/decisions')) {
      policyAttempts += 1;
      policyKeys.push(request.headers()['idempotency-key']);
      if (policyAttempts === 1) return json(route, { detail: 'temporariamente indisponível' }, 503);
      return json(route, {
        ...financialPolicy,
        policy_id: 17,
        financial_state_snapshot_id: 7,
        created_at: '2026-09-08T12:00:01Z',
      }, 201);
    }
    if (path.endsWith('/households/10/financial-policy')) return json(route, financialPolicy);
    if (path.endsWith('/households/10/financial-state/snapshots')) {
      snapshotAttempts += 1;
      snapshotKeys.push(request.headers()['idempotency-key']);
      if (snapshotAttempts === 1) return json(route, { detail: 'temporariamente indisponível' }, 503);
      return json(route, { id: 99 });
    }
    if (path.endsWith('/households/10/financial-state')) return json(route, financialState);
    if (path.endsWith('/households/10/incomes')) {
      if (request.method() === 'POST') {
        incomePayloads.push(request.postDataJSON());
        return json(route, { id: 11 }, 201);
      }
      return json(route, []);
    }
    if (path.endsWith('/households/10/expenses')) return json(route, []);
    return json(route, { detail: 'fixture não configurada' }, 404);
  });

  await seedSession(page);
  await page.goto('/financial');

  await expect(page.getByRole('heading', { name: 'Minha situação financeira' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Sua prioridade agora' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Plano deste período' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Como investir este valor' })).toBeVisible();
  await expect(page.getByText('Não há capital comprovadamente liberado para novos investimentos.')).toBeVisible();
  await expect(page.getByText('Capital disponível no período')).toBeVisible();
  await expect(
    page.getByRole('list', { name: 'Plano de capital do período' })
      .getByText('Reserva de emergência', { exact: true }),
  ).toBeVisible();
  await expect(page.getByRole('heading', { level: 3, name: /4\.000,00/ })).toBeVisible();
  await expect(page.getByText('LIMITADO', { exact: true })).toBeVisible();
  await expect(page.getByText('Sua reserva atual cobre 3 meses e ainda está abaixo do alvo vigente.')).toBeVisible();
  await expect(page.getByText(/Investir somente o capital excedente/)).toBeVisible();
  await expect(page.getByText(/Variáveis: Não informado/)).toBeVisible();
  await expect(page.getByText(/Dívidas:.*0,00/)).toBeVisible();

  await page.getByRole('button', { name: 'Nova receita' }).click();
  await page.getByLabel('Descrição').fill('Renda compartilhada');
  await page.getByLabel('Valor').fill('2500');
  await page.getByLabel('Pertence a').selectOption('HOUSEHOLD');
  await page.getByRole('button', { name: 'Salvar receita' }).click();
  await expect(page.getByRole('status').filter({ hasText: 'Receita cadastrada' })).toContainText('Receita cadastrada');
  expect(incomePayloads).toEqual([expect.objectContaining({ ownership_scope: 'HOUSEHOLD', amount: 2500 })]);

  await page.getByRole('button', { name: 'Salvar retrato' }).click();
  await expect(page.getByText('Não foi possível salvar o retrato')).toBeVisible();
  await page.getByRole('button', { name: 'Tentar salvar novamente' }).click();
  await expect(page.getByText('Retrato financeiro salvo no histórico.')).toBeVisible();
  expect(snapshotKeys).toHaveLength(2);
  expect(snapshotKeys[0]).toBeTruthy();
  expect(snapshotKeys[1]).toBe(snapshotKeys[0]);

  await page.getByRole('button', { name: 'Salvar decisão' }).click();
  await expect(page.getByText('Não foi possível salvar a decisão')).toBeVisible();
  await page.getByRole('button', { name: 'Tentar novamente' }).last().click();
  await expect(page.getByText('Decisão financeira salva no histórico.')).toBeVisible();
  expect(policyKeys).toHaveLength(2);
  expect(policyKeys[0]).toBeTruthy();
  expect(policyKeys[1]).toBe(policyKeys[0]);

  await page.getByRole('button', { name: 'Salvar plano' }).click();
  await expect(page.getByText('Não foi possível salvar o plano')).toBeVisible();
  await page.getByRole('button', { name: 'Tentar novamente' }).last().click();
  await expect(page.getByText('Plano de capital salvo no histórico.')).toBeVisible();
  expect(allocationKeys).toHaveLength(2);
  expect(allocationKeys[0]).toBeTruthy();
  expect(allocationKeys[1]).toBe(allocationKeys[0]);

  await page.getByRole('button', { name: 'Salvar estratégia' }).click();
  await expect(page.getByText('Não foi possível salvar a estratégia')).toBeVisible();
  await page.getByRole('button', { name: 'Tentar novamente' }).last().click();
  await expect(page.getByText('Estratégia de investimento salva no histórico.')).toBeVisible();
  expect(orchestrationKeys).toHaveLength(2);
  expect(orchestrationKeys[0]).toBeTruthy();
  expect(orchestrationKeys[1]).toBe(orchestrationKeys[0]);
});
