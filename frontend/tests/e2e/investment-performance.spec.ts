import { expect, test, type Page, type Route } from '@playwright/test';
import {
  authenticatedUser,
  decisionDetailResponse,
  decisionHistoryResponse,
  fakeAccessToken,
} from '../fixtures/investmentFixtures';

const headers = {
  'access-control-allow-origin': 'http://127.0.0.1:4173',
  'access-control-allow-headers': 'authorization,content-type',
  'access-control-allow-methods': 'GET,OPTIONS',
};

async function json(route: Route, body: unknown, status = 200) {
  if (route.request().method() === 'OPTIONS') return route.fulfill({ status: 204, headers });
  return route.fulfill({ status, headers, contentType: 'application/json', body: JSON.stringify(body) });
}

async function authenticated(page: Page) {
  const token = fakeAccessToken();
  await page.goto('/login');
  await page.evaluate(({ accessToken, user }) => {
    window.localStorage.setItem('vinance_access_token', accessToken);
    window.localStorage.setItem('vinance_user', JSON.stringify(user));
  }, { accessToken: token, user: authenticatedUser });
  await page.route('**/api/v1/me', (route) => json(route, authenticatedUser));
  return token;
}

function metric(key: string, overrides = {}) {
  return {
    key,
    total: 1,
    total_eligible: 1,
    evaluated: 1,
    pending: 0,
    average_return_pct: 4,
    median_return_pct: 4,
    positive_pct: 100,
    negative_pct: 0,
    directional_accuracy_pct: 100,
    directional_sample: 1,
    neutral: 0,
    ...overrides,
  };
}

const performanceSummary = {
  as_of: '2026-08-26T12:00:00Z',
  selected_horizon: null,
  total_decisions: 1,
  eligible_decisions: 3,
  evaluated: 1,
  pending: 2,
  average_return_pct: 4,
  median_return_pct: 4,
  positive_pct: 100,
  negative_pct: 0,
  directional_accuracy_pct: 100,
  directional_sample: 1,
  by_horizon: [metric('1d'), metric('7d', { total: 0, evaluated: 0, pending: 1, average_return_pct: null, directional_accuracy_pct: null }), metric('30d', { total: 0, evaluated: 0, pending: 1, average_return_pct: null, directional_accuracy_pct: null })],
  by_action: [metric('BUY')],
  by_asset: [metric('GARE11')],
  by_risk: [metric('LOW')],
  by_confidence: [metric('HIGH')],
  by_score_band: [metric('HIGH')],
  by_profile: [metric('CONSERVATIVE')],
  by_rule_version: [metric('investment-decision-presentation-v1')],
  by_recommendation_engine_version: [metric('budget-advisor-v1')],
  by_score_version: [metric('vinance_score_v1')],
  by_guardrail_version: [metric('vinance_guardrail_v1')],
  by_version_cohort: [metric('budget-advisor-v1 | investment-decision-presentation-v1 | vinance_score_v1 | vinance_guardrail_v1')],
  mixed_versions: false,
  calibration: [metric('HIGH', { mean_confidence: 100, calibration_gap_pct: 0, diagnostic: 'INSUFFICIENT_SAMPLE' })],
  calibration_summary: { interpretation: 'INSUFFICIENT_SAMPLE' },
  timeline: [metric('2026-08:1d', { period: '2026-08', horizon: '1d' })],
};

const decisionPerformance = {
  decision_id: decisionDetailResponse.decision_id,
  asset: 'GARE11',
  action: 'BUY',
  decision_created_at: decisionDetailResponse.created_at,
  risk_level: 'LOW',
  confidence: '100',
  trend: 'UPTREND',
  recommendation_score: '87.3',
  investor_profile: 'CONSERVATIVE',
  rule_version: 'investment-decision-presentation-v1',
  recommendation_engine_version: 'budget-advisor-v1',
  score_version: 'vinance_score_v1',
  guardrail_version: 'vinance_guardrail_v1',
  reference_price: '8.23',
  reference_price_timestamp: decisionDetailResponse.created_at,
  price_source: 'decision_snapshot',
  evaluations: [{
    horizon: '1d',
    reference_price: '8.23',
    reference_price_timestamp: decisionDetailResponse.created_at,
    price_source: 'decision_snapshot',
    evaluation_price: '8.5592',
    evaluation_timestamp: '2026-08-26T23:59:59Z',
    evaluation_price_source: 'brapi',
    absolute_change: '0.3292',
    return_pct: '4',
    max_favorable_excursion_pct: '6',
    max_adverse_excursion_pct: '-2',
    result_status: 'EVALUATED',
    result_classification: 'CORRECT',
    result_context: { action: 'BUY' },
    evaluation_policy_version: 'decision-performance-v1',
    evaluated_at: '2026-08-27T05:30:00Z',
  }],
  pending_horizons: ['7d', '30d'],
  eligible_pending_horizons: [],
  immature_horizons: ['7d', '30d'],
};

test('painel geral consulta analytics autenticado e usa linguagem observacional', async ({ page }) => {
  const token = await authenticated(page);
  let authorization = '';
  await page.route('**/api/v1/investments/performance', async (route) => {
    authorization = route.request().headers().authorization ?? '';
    await json(route, performanceSummary);
  });

  await page.goto('/investir');
  await expect(page.getByRole('heading', { name: 'Central de decisão de investimentos' })).toBeVisible();
  await page.getByRole('button', { name: /Ver performance/ }).click();
  await expect(page.getByText('Avaliações concluídas')).toBeVisible();
  await expect(page.getByText('Retorno observado médio')).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Por horizonte' })).toBeVisible();
  await expect(page.getByText(/Não representa operação executada/)).toBeVisible();
  expect(authorization).toBe(`Bearer ${token}`);
  await expect(page.getByText(/lucro garantido/i)).toHaveCount(0);
  for (const viewport of [{ width: 1440, height: 900 }, { width: 390, height: 844 }, { width: 320, height: 720 }]) {
    await page.setViewportSize(viewport);
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    expect(overflow, JSON.stringify(viewport)).toBeLessThanOrEqual(0);
  }
});

test('snapshot histórico abre resultados 1d e mantém 7d e 30d pendentes', async ({ page }) => {
  await authenticated(page);
  await page.route('**/api/v1/investments/decisions?**', (route) => json(route, decisionHistoryResponse));
  await page.route(new RegExp('/api/v1/investments/decisions/[0-9a-f-]{36}$'), (route) => json(route, decisionDetailResponse));
  await page.route('**/api/v1/investments/decisions/*/performance', (route) => json(route, decisionPerformance));

  await page.goto('/investir');
  await page.getByRole('button', { name: 'Ver histórico' }).click();
  await page.getByRole('button', { name: /GARE11/ }).click();
  await expect(page.getByText('Snapshot imutável')).toBeVisible();
  await page.getByRole('button', { name: 'Ver resultados posteriores' }).click();
  await expect(page.getByText('O que aconteceu depois')).toBeVisible();
  await expect(page.getByText('+4,00%')).toBeVisible();
  await expect(page.getByText('Coerente')).toBeVisible();
  await expect(page.getByText('Pendentes: 7 dias, 30 dias.')).toBeVisible();
  await expect(page.getByText(/Não é resultado de uma operação real/)).toBeVisible();
});
