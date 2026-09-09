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
  household_id: 10,
  engine_version: 'financial-policy-v1',
  rules_version: 'financial-policy-rules-v1',
  evaluated_at: '2026-09-08T12:00:00Z',
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
  evidence: [], rules_evaluated: [], ruleset: {}, source_financial_state: {}, previous_financial_state: {},
};

test('financial state preserva ausência, ownership e idempotência de snapshot', async ({ page }) => {
  const incomePayloads: unknown[] = [];
  const snapshotKeys: string[] = [];
  let snapshotAttempts = 0;

  await page.route('**/api/v1/me', (route) => json(route, authenticatedUser));
  await page.route('**/api/v1/financial/**', async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    if (request.method() === 'OPTIONS') return json(route, null);
    if (path.endsWith('/financial/profile')) return json(route, { id: 1 });
    if (path.endsWith('/households/default')) return json(route, household);
    if (path.endsWith('/financial/households')) return json(route, [household]);
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
  await expect(page.getByRole('heading', { name: 'Prioridades financeiras agora' })).toBeVisible();
  await expect(page.getByText('Novos aportes limitados')).toBeVisible();
  await expect(page.getByText(/1\. Fortalecer a reserva de emergência/)).toBeVisible();
  await expect(page.getByText(/2\. Investir somente o capital excedente/)).toBeVisible();
  await expect(page.getByText(/Variáveis: Não informado/)).toBeVisible();
  await expect(page.getByText(/Dívidas:.*0,00/)).toBeVisible();

  await page.getByRole('button', { name: 'Nova receita' }).click();
  await page.getByLabel('Descrição').fill('Renda compartilhada');
  await page.getByLabel('Valor').fill('2500');
  await page.getByLabel('Pertence a').selectOption('HOUSEHOLD');
  await page.getByRole('button', { name: 'Salvar receita' }).click();
  await expect(page.getByRole('status')).toContainText('Receita cadastrada');
  expect(incomePayloads).toEqual([expect.objectContaining({ ownership_scope: 'HOUSEHOLD', amount: 2500 })]);

  await page.getByRole('button', { name: 'Salvar retrato' }).click();
  await expect(page.getByText('Não foi possível salvar o retrato')).toBeVisible();
  await page.getByRole('button', { name: 'Tentar salvar novamente' }).click();
  await expect(page.getByText('Retrato financeiro salvo no histórico.')).toBeVisible();
  expect(snapshotKeys).toHaveLength(2);
  expect(snapshotKeys[0]).toBeTruthy();
  expect(snapshotKeys[1]).toBe(snapshotKeys[0]);
});
