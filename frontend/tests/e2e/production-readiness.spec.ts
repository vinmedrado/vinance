import { expect, test, type Page, type Route } from '@playwright/test';
import {
  authenticatedUser,
  completeBudgetResponse,
  decisionDetailResponse,
  decisionHistoryResponse,
  fakeAccessToken,
} from '../fixtures/investmentFixtures';

const apiHeaders = {
  'access-control-allow-origin': 'http://127.0.0.1:4173',
  'access-control-allow-headers': 'authorization,content-type,x-decision-id,x-correlation-id',
  'access-control-expose-headers': 'x-decision-id,x-correlation-id',
  'access-control-allow-methods': 'GET,POST,PATCH,DELETE,OPTIONS',
};
const alertId = '38000000-0000-4000-8000-000000000001';
const alertDecisionId = '38000000-0000-4000-8000-000000000002';

async function json(route: Route, body: unknown, status = 200) {
  if (route.request().method() === 'OPTIONS') {
    await route.fulfill({ status: 204, headers: apiHeaders });
    return;
  }
  await route.fulfill({ status, headers: apiHeaders, contentType: 'application/json', body: JSON.stringify(body) });
}

function metric(key: string) {
  return {
    key, total: 1, total_eligible: 1, evaluated: 1, pending: 0,
    average_return_pct: 4, median_return_pct: 4, positive_pct: 100,
    negative_pct: 0, directional_accuracy_pct: 100, directional_sample: 1, neutral: 0,
  };
}

test('aceite completo: login, decisão, auditoria, performance, alerta, reload e logout', async ({ page }) => {
  test.setTimeout(60_000);
  const consoleErrors: string[] = [];
  const pageErrors: string[] = [];
  page.on('console', (message) => {
    if (message.type() === 'error') consoleErrors.push(message.text());
  });
  page.on('pageerror', (error) => pageErrors.push(error.message));

  const token = fakeAccessToken();
  let monitored = false;
  let generated = false;
  let readAt: string | null = null;
  const subscription = () => ({
    id: 38,
    asset: 'GARE11',
    market: 'FII',
    budget: '300.00',
    investor_profile: 'CONSERVATIVE',
    source_decision_id: completeBudgetResponse.decision_id,
    enabled: true,
    alert_on_action_change: true,
    alert_on_score_change: true,
    alert_on_confidence_change: true,
    alert_on_risk_change: true,
    alert_on_new_opportunity: true,
    minimum_score_delta: '5',
    minimum_confidence_delta: '10',
    cooldown_minutes: 180,
    rule_version: 'investment-alerts-v1',
    created_at: '2026-08-27T12:00:00Z',
    updated_at: '2026-08-27T12:00:00Z',
  });
  const alert = () => ({
    alert_id: alertId,
    subscription_id: 38,
    decision_id: alertDecisionId,
    asset: 'GARE11',
    alert_type: 'NEW_OPPORTUNITY',
    severity: 'HIGH',
    delivery_channel: 'IN_APP',
    message: 'A recomendação mudou de Aguardar para Comprar.',
    created_at: '2026-08-27T12:30:00Z',
    read_at: readAt,
    previous_state: { action: 'WAIT', score: '70', confidence: '80', risk_level: 'LOW', trend: 'SIDEWAYS' },
    current_state: { action: 'BUY', score: '87.3', confidence: '100', risk_level: 'LOW', trend: 'UPTREND' },
    rule_version: 'investment-alerts-v1',
  });

  await page.route('**/api/v1/login', (route) => json(route, { access_token: token, token_type: 'bearer', user: authenticatedUser }));
  await page.route('**/api/v1/me', (route) => json(route, authenticatedUser));
  await page.route('**/api/intelligence/budget-advisor**', (route) => json(route, completeBudgetResponse));
  await page.route('**/api/v1/investments/decisions?**', (route) => json(route, decisionHistoryResponse));
  await page.route(new RegExp('/api/v1/investments/decisions/[0-9a-f-]{36}$'), (route) => json(route, decisionDetailResponse));
  await page.route('**/api/v1/investments/decisions/*/performance', (route) => json(route, {
    decision_id: completeBudgetResponse.decision_id,
    asset: 'GARE11', action: 'BUY', decision_created_at: completeBudgetResponse.generated_at,
    risk_level: 'LOW', confidence: '100', trend: 'UPTREND', recommendation_score: '87.3',
    investor_profile: 'CONSERVATIVE', rule_version: 'investment-decision-presentation-v1',
    recommendation_engine_version: 'budget-advisor-v1', score_version: 'vinance_score_v1',
    guardrail_version: 'vinance_guardrail_v1', reference_price: '8.23',
    reference_price_timestamp: completeBudgetResponse.generated_at, price_source: 'decision_snapshot',
    evaluations: [], pending_horizons: ['1d', '7d', '30d'], eligible_pending_horizons: [], immature_horizons: ['1d', '7d', '30d'],
  }));
  await page.route('**/api/v1/investments/performance', (route) => json(route, {
    as_of: '2026-08-27T12:00:00Z', selected_horizon: null, total_decisions: 1,
    eligible_decisions: 1, evaluated: 1, pending: 0, average_return_pct: 4,
    median_return_pct: 4, positive_pct: 100, negative_pct: 0,
    directional_accuracy_pct: 100, directional_sample: 1,
    by_horizon: [metric('1d')], by_action: [metric('BUY')], by_asset: [metric('GARE11')],
    by_risk: [metric('LOW')], by_confidence: [metric('HIGH')], by_score_band: [metric('HIGH')],
    by_profile: [metric('CONSERVATIVE')], by_rule_version: [metric('investment-decision-presentation-v1')],
    by_recommendation_engine_version: [metric('budget-advisor-v1')], by_score_version: [metric('vinance_score_v1')],
    by_guardrail_version: [metric('vinance_guardrail_v1')], by_version_cohort: [], mixed_versions: false,
    calibration: [], calibration_summary: { interpretation: 'INSUFFICIENT_SAMPLE' }, timeline: [],
  }));
  await page.route(/\/api\/v1\/investments\/alert-subscriptions(?:\/[^?]*)?(?:\?.*)?$/, async (route) => {
    const method = route.request().method();
    if (method === 'OPTIONS') return json(route, {});
    if (method === 'GET') return json(route, { items: monitored ? [subscription()] : [], total: monitored ? 1 : 0, active: monitored ? 1 : 0, limit: 20 });
    if (method === 'POST') {
      monitored = true;
      generated = true;
      return json(route, subscription(), 201);
    }
    if (method === 'DELETE') {
      monitored = false;
      return route.fulfill({ status: 204, headers: apiHeaders });
    }
    return json(route, subscription());
  });
  await page.route(/\/api\/v1\/investments\/alerts(?:\/[^?]*)?(?:\?.*)?$/, async (route) => {
    const method = route.request().method();
    const url = new URL(route.request().url());
    if (method === 'OPTIONS') return json(route, {});
    if (url.pathname.endsWith('/read')) {
      readAt = '2026-08-27T12:35:00Z';
      return json(route, alert());
    }
    if (url.pathname.endsWith(`/${alertId}`)) return json(route, alert());
    const visible = generated && !(url.searchParams.get('unread_only') === 'true' && readAt);
    return json(route, {
      items: visible ? [alert()] : [], page: Number(url.searchParams.get('page') ?? 1),
      page_size: Number(url.searchParams.get('page_size') ?? 8), total: visible ? 1 : 0,
      total_pages: visible ? 1 : 0, unread_count: generated && !readAt ? 1 : 0,
    });
  });

  await page.goto('/investir');
  await expect(page).toHaveURL(/\/login$/);
  await page.getByLabel('E-mail').fill('fase38@fixture.local');
  await page.getByLabel('Senha').fill('fixture-segura-38');
  await page.getByRole('button', { name: 'Entrar', exact: true }).click();
  await expect(page).toHaveURL(/\/investir$/);

  await page.getByRole('button', { name: 'Analisar orçamento' }).click();
  await expect(page.getByRole('heading', { name: 'GARE11' })).toBeVisible();
  await page.getByText('Decisão registrada').click();
  await expect(page.getByText(completeBudgetResponse.decision_id)).toBeVisible();

  await page.getByRole('button', { name: /Ver performance/ }).click();
  await expect(page.getByText('Avaliações concluídas')).toBeVisible();
  await page.getByRole('button', { name: /Ver histórico/ }).click();
  await page.getByRole('button', { name: /GARE11/ }).click();
  await expect(page.getByText('Snapshot imutável')).toBeVisible();
  const historyDetail = page.locator('aside.vn-history-detail');
  await historyDetail.getByText('Rastreabilidade completa').click();
  await expect(historyDetail.getByText(completeBudgetResponse.decision_id)).toBeVisible();

  await page.reload();
  await expect(page).toHaveURL(/\/investir$/);
  await page.getByRole('button', { name: /Ver histórico/ }).click();
  await expect(page.getByRole('button', { name: /GARE11/ })).toBeVisible();

  await page.getByRole('button', { name: 'Analisar orçamento' }).click();
  await expect(page.getByRole('heading', { name: 'GARE11' })).toBeVisible();
  await page.getByRole('button', { name: /Monitorar ativo/ }).click();
  await expect(page.getByText('Monitoramento ativo')).toBeVisible();
  await page.getByRole('button', { name: /Abrir alertas/ }).click();
  await page.getByRole('button', { name: /A recomendação mudou de Aguardar/ }).click();
  await expect(page.locator('aside.vn-alert-detail')).toContainText(alertDecisionId);
  await page.getByRole('button', { name: 'Marcar como lido' }).click();
  await expect(page.getByLabel('1 alertas não lidos')).toHaveCount(0);

  for (const viewport of [
    { width: 1440, height: 900 },
    { width: 768, height: 1024 },
    { width: 390, height: 844 },
    { width: 320, height: 720 },
  ]) {
    await page.setViewportSize(viewport);
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    expect(overflow, JSON.stringify(viewport)).toBeLessThanOrEqual(0);
  }

  await page.reload();
  await expect(page).toHaveURL(/\/investir$/);
  await page.getByRole('button', { name: /Sair/ }).click();
  await expect(page).toHaveURL(/\/login$/);
  await page.goto('/investir');
  await expect(page).toHaveURL(/\/login$/);
  expect(consoleErrors).toEqual([]);
  expect(pageErrors).toEqual([]);
});
