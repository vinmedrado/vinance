import { expect, test, type Page, type Route } from '@playwright/test';
import {
  authenticatedUser,
  completeBudgetResponse,
  fakeAccessToken,
} from '../fixtures/investmentFixtures';


const decisionId = completeBudgetResponse.decision_id;
const alertId = '37000000-0000-4000-8000-000000000002';
const createdAt = '2026-08-27T01:00:00Z';
const headers = {
  'access-control-allow-origin': 'http://127.0.0.1:4173',
  'access-control-allow-headers': 'authorization,content-type,x-decision-id,x-correlation-id',
  'access-control-allow-methods': 'GET,POST,PATCH,DELETE,OPTIONS',
};

async function json(route: Route, body: unknown, status = 200) {
  if (route.request().method() === 'OPTIONS') return route.fulfill({ status: 204, headers });
  return route.fulfill({ status, headers, contentType: 'application/json', body: JSON.stringify(body) });
}

async function authenticate(page: Page) {
  const token = fakeAccessToken();
  await page.goto('/login');
  await page.evaluate(({ accessToken, user }) => {
    window.localStorage.setItem('vinance_access_token', accessToken);
    window.localStorage.setItem('vinance_user', JSON.stringify(user));
  }, { accessToken: token, user: authenticatedUser });
  await page.route('**/api/v1/me', (route) => json(route, authenticatedUser));
  return token;
}

test('subscription gera avaliação isolada, alerta in-app, leitura e desativação sem ordem', async ({ page }) => {
  const token = await authenticate(page);
  let monitored = false;
  let alertGeneratedByFixtureEvaluation = false;
  let readAt: string | null = null;
  let subscriptionAuthorization = '';
  let alertAuthorization = '';

  const subscription = () => ({
    id: 7,
    asset: 'GARE11',
    market: 'FII',
    budget: '300.00',
    investor_profile: 'CONSERVATIVE',
    source_decision_id: decisionId,
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
    created_at: createdAt,
    updated_at: createdAt,
  });
  const alert = () => ({
    alert_id: alertId,
    subscription_id: monitored ? 7 : null,
    decision_id: '37000000-0000-4000-8000-000000000099',
    asset: 'GARE11',
    alert_type: 'NEW_OPPORTUNITY',
    severity: 'HIGH',
    delivery_channel: 'IN_APP',
    message: 'A recomendação mudou de Aguardar para Comprar.',
    created_at: createdAt,
    read_at: readAt,
    previous_state: { action: 'WAIT', score: '70', confidence: '80', risk_level: 'LOW', trend: 'SIDEWAYS' },
    current_state: { action: 'BUY', score: '82', confidence: '92', risk_level: 'LOW', trend: 'UPTREND' },
    rule_version: 'investment-alerts-v1',
  });

  await page.route('**/api/intelligence/budget-advisor**', (route) => json(route, completeBudgetResponse));
  await page.route(/\/api\/v1\/investments\/alert-subscriptions(?:\/[^?]*)?(?:\?.*)?$/, async (route) => {
    if (route.request().method() !== 'OPTIONS') subscriptionAuthorization = route.request().headers().authorization ?? '';
    const method = route.request().method();
    if (method === 'OPTIONS') return json(route, {});
    if (method === 'GET') {
      return json(route, { items: monitored ? [subscription()] : [], total: monitored ? 1 : 0, active: monitored ? 1 : 0, limit: 20 });
    }
    if (method === 'POST') {
      const body = route.request().postDataJSON();
      expect(body).toEqual({ asset: 'GARE11', source_decision_id: decisionId });
      monitored = true;
      // Isolated fixture override: represents the official periodic evaluator finding WAIT -> BUY.
      alertGeneratedByFixtureEvaluation = true;
      return json(route, subscription(), 201);
    }
    if (method === 'DELETE') {
      monitored = false;
      return route.fulfill({ status: 204, headers });
    }
    return json(route, subscription());
  });
  await page.route(/\/api\/v1\/investments\/alerts(?:\/[^?]*)?(?:\?.*)?$/, async (route) => {
    if (route.request().method() !== 'OPTIONS') alertAuthorization = route.request().headers().authorization ?? '';
    const url = new URL(route.request().url());
    const method = route.request().method();
    if (method === 'OPTIONS') return json(route, {});
    if (url.pathname.endsWith('/read') && method === 'PATCH') {
      readAt = '2026-08-27T01:05:00Z';
      return json(route, alert());
    }
    if (url.pathname.endsWith(`/${alertId}`)) return json(route, alert());
    const visible = alertGeneratedByFixtureEvaluation && !(url.searchParams.get('unread_only') === 'true' && readAt);
    return json(route, {
      items: visible ? [alert()] : [],
      page: Number(url.searchParams.get('page') ?? 1),
      page_size: Number(url.searchParams.get('page_size') ?? 8),
      total: visible ? 1 : 0,
      total_pages: visible ? 1 : 0,
      unread_count: alertGeneratedByFixtureEvaluation && !readAt ? 1 : 0,
    });
  });

  await page.goto('/investir');
  await expect(page.getByRole('heading', { name: 'Central de decisão de investimentos' })).toBeVisible();
  await page.getByRole('button', { name: 'Analisar orçamento' }).click();
  await expect(page.getByRole('heading', { name: 'GARE11' })).toBeVisible();

  await page.getByRole('button', { name: /Monitorar ativo/ }).click();
  await expect(page.getByText('Monitoramento ativo')).toBeVisible();
  expect(monitored).toBe(true);
  expect(alertGeneratedByFixtureEvaluation).toBe(true);
  expect(subscriptionAuthorization).toBe(`Bearer ${token}`);

  await expect(page.getByLabel('1 alertas não lidos')).toBeVisible();
  await page.getByRole('button', { name: /Abrir alertas/ }).click();
  await expect(page.getByText('Nova oportunidade')).toBeVisible();
  await expect(page.getByText('A recomendação mudou de Aguardar para Comprar.')).toBeVisible();
  await page.getByRole('button', { name: /A recomendação mudou de Aguardar/ }).click();
  const detail = page.locator('aside.vn-alert-detail');
  await expect(detail.getByRole('heading', { name: 'GARE11' })).toBeVisible();
  await expect(detail.getByLabel('Antes')).toContainText('Aguardar');
  await expect(detail.getByLabel('Agora')).toContainText('Comprar');
  await expect(detail.getByText('37000000-0000-4000-8000-000000000099')).toBeVisible();
  expect(alertAuthorization).toBe(`Bearer ${token}`);

  for (const viewport of [{ width: 390, height: 844 }, { width: 320, height: 720 }]) {
    await page.setViewportSize(viewport);
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    expect(overflow, JSON.stringify(viewport)).toBeLessThanOrEqual(0);
  }

  await detail.getByRole('button', { name: 'Marcar como lido' }).click();
  await expect(page.getByLabel('1 alertas não lidos')).toHaveCount(0);
  expect(readAt).not.toBeNull();

  await page.getByRole('button', { name: /Configurar/ }).click();
  await page.getByRole('button', { name: /Excluir monitoramento/ }).click();
  await expect(page.getByText('GARE11 deixou de ser monitorado.')).toBeVisible();
  expect(monitored).toBe(false);

  await expect(page.getByText(/compre agora/i)).toHaveCount(0);
  await expect(page.getByText(/lucro garantido/i)).toHaveCount(0);
  await page.getByRole('button', { name: /Sair/ }).click();
  await expect(page).toHaveURL(/\/login$/);
  await page.goto('/investir');
  await expect(page).toHaveURL(/\/login$/);
});
