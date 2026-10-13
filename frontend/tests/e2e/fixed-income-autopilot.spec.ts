import { expect, test, type Page, type Route } from '@playwright/test';

import {
  authenticatedUser,
  fakeAccessToken,
} from '../fixtures/investmentFixtures';
import { mockBrowserSession } from '../fixtures/authSessionFixture';

const apiHeaders = {
  'access-control-allow-origin': 'http://127.0.0.1:4173',
  'access-control-allow-headers': 'authorization,content-type',
  'access-control-allow-methods': 'GET,OPTIONS',
};

async function json(route: Route, body: unknown, status = 200) {
  if (route.request().method() === 'OPTIONS') {
    await route.fulfill({ status: 204, headers: apiHeaders });
    return;
  }
  await route.fulfill({
    status,
    headers: apiHeaders,
    contentType: 'application/json',
    body: JSON.stringify(body),
  });
}

async function seedSession(page: Page) {
  await mockBrowserSession(page, { token: fakeAccessToken(), user: authenticatedUser, headers: apiHeaders });
}

const fixedIncomeOrchestration = {
  orchestration_id: 31,
  household_id: 10,
  financial_state_snapshot_id: 7,
  financial_policy_decision_id: 17,
  capital_allocation_decision_id: 23,
  engine_version: 'investment-orchestrator-v1',
  rules_version: 'investment-orchestrator-rules-v1',
  status: 'ACTIVE',
  currency: 'BRL',
  investment_budget: '1000.00',
  profile_context: { status: 'COMPLETE', effective_profile: 'MODERATE' },
  portfolio_context: { status: 'PARTIAL' },
  market_context: { status: 'FRESH', as_of: '2026-10-09T20:15:00Z' },
  asset_class_decisions: [{
    asset_class: 'FIXED_INCOME', eligibility: 'ELIGIBLE', reason: 'Produto compatível com o contexto conhecido.',
  }],
  class_allocations: [{
    asset_class: 'FIXED_INCOME', market: 'FIXED_INCOME', allocated_amount: '800.00',
  }],
  ranked_opportunities: [{
    asset_id: 31,
    symbol: 'Tesouro Selic 2031',
    ticker: 'tesouro-selic-2031',
    asset_class: 'FIXED_INCOME',
    market: 'FIXED_INCOME',
    action: 'BUY',
    rank: 1,
    price_reference: '15000.00',
    quantity_candidate: null,
    quantity_suggested: null,
    capital_required: '150.00',
    capital_committed: '800.00',
    recommendation_score: '90',
    risk_level: 'LOW',
    trend_label: null,
    momentum_score: null,
    confidence: '90',
    guardrail_status: 'APPROVED',
    reason: 'Aporte dentro do orçamento autorizado e do mínimo conhecido.',
    reasons: ['Aporte dentro do orçamento autorizado e do mínimo conhecido.'],
    warnings: [],
    source_product_id: 'tesouro-selic-2031:2031-03-01',
    product_name: 'Tesouro Selic 2031',
    product_type: 'TREASURY_SELIC',
    indexer: 'SELIC',
    reference_rate: '0.05',
    maturity_date: '2031-03-01',
    liquidity_type: 'DAILY_REPURCHASE',
    minimum_investment: '150.00',
    guarantee_type: 'SOVEREIGN_ISSUER',
    market_date: '2026-10-09',
    freshness_status: 'FRESH',
  }],
  suggested_capital: '800.00',
  remaining_investment_cash: '200.00',
  speculative_capital: '0.00',
  trading_dispatch: false,
  blockers: [],
  warnings: [],
  missing_information: [],
  evidence: [],
  rule_traces: [],
  state_fingerprint: '1'.repeat(64),
  policy_fingerprint: '2'.repeat(64),
  allocation_fingerprint: '3'.repeat(64),
  market_context_fingerprint: '4'.repeat(64),
  ruleset_fingerprint: '5'.repeat(64),
  decision_fingerprint: '6'.repeat(64),
  generated_at: '2026-10-09T20:15:00Z',
  created_at: '2026-10-09T20:15:01Z',
};

const actionPlan = {
  action_plan_id: 41,
  household_id: 10,
  status: 'READY',
  summary: {
    primary_action: 'Avaliar o Tesouro Selic com o capital autorizado.',
  },
  generated_at: '2026-10-09T20:15:00Z',
};

test('apresenta renda fixa real do Orchestrator no contexto congelado do Action Plan', async ({ page }) => {
  await page.route('**/api/v1/me', (route) => json(route, authenticatedUser));
  await page.route(
    '**/api/v1/financial/households/10/investment-orchestration',
    (route) => json(route, fixedIncomeOrchestration),
  );
  await page.route(
    '**/api/v1/financial/households/10/action-plan/history/41',
    (route) => json(route, actionPlan),
  );

  await seedSession(page);
  await page.goto('/investir?modo=autopilot&household_id=10&action_plan_id=41');

  await expect(page.getByRole('heading', { name: 'Central de decisão de investimentos' })).toBeVisible();
  await expect(page.getByText('Origem no plano de ação')).toBeVisible();
  await expect(page.getByText('Avaliar o Tesouro Selic com o capital autorizado.')).toBeVisible();
  await expect(page.getByText('Renda fixa avaliada pelo Autopilot')).toBeVisible();

  const opportunity = page.getByRole('list', { name: 'Oportunidades de renda fixa do Autopilot' });
  await expect(opportunity).toContainText('Tesouro Selic 2031');
  await expect(opportunity).toContainText('Comprar');
  await expect(opportunity).toContainText('R$ 800,00');
  await expect(opportunity).toContainText('Tesouro Selic · SELIC');
  await expect(opportunity).toContainText('Recompra diária a preço de mercado');
  await expect(opportunity).toContainText('Emissor soberano — não é FGC');
  await expect(opportunity).toContainText('não promessa de retorno');
  await expect(page.getByText('Nenhuma ordem é executada.')).toBeVisible();
});
