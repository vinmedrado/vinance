import { expect, test, type Page, type Request, type Route } from '@playwright/test';
import {
  authenticatedUser,
  completeBudgetResponse,
  decisionDetailResponse,
  decisionHistoryResponse,
  fakeAccessToken,
  longContentResponse,
} from '../fixtures/investmentFixtures';

const apiHeaders = {
  'access-control-allow-origin': 'http://127.0.0.1:4173',
  'access-control-allow-headers': 'authorization,content-type,x-decision-id,x-correlation-id',
  'access-control-expose-headers': 'x-decision-id,x-correlation-id',
  'access-control-allow-methods': 'GET,POST,OPTIONS',
};

async function json(route: Route, body: unknown, status = 200) {
  if (route.request().method() === 'OPTIONS') {
    await route.fulfill({ status: 204, headers: apiHeaders });
    return;
  }
  await route.fulfill({ status, headers: apiHeaders, contentType: 'application/json', body: JSON.stringify(body) });
}

async function seedSession(page: Page, expiresAt?: number) {
  const token = fakeAccessToken(expiresAt);
  await page.goto('/login');
  await page.evaluate(({ accessToken, user }) => {
    window.localStorage.setItem('vinance_access_token', accessToken);
    window.localStorage.setItem('vinance_user', JSON.stringify(user));
  }, { accessToken: token, user: authenticatedUser });
  return token;
}

async function mockMe(page: Page, status = 200, onRequest?: (request: Request) => void) {
  await page.route('**/api/v1/me', (route) => {
    if (route.request().method() !== 'OPTIONS') onRequest?.(route.request());
    return json(route, status === 200 ? authenticatedUser : { detail: 'Invalid token' }, status);
  });
}

async function mockBudget(page: Page, payload: unknown = completeBudgetResponse, onRequest?: (request: Request) => void) {
  await page.route('**/api/intelligence/budget-advisor**', async (route) => {
    if (route.request().method() !== 'OPTIONS') onRequest?.(route.request());
    await json(route, payload);
  });
}

test('anônimo é redirecionado e login retorna para /investir', async ({ page }) => {
  await mockMe(page);
  await page.route('**/api/v1/login', (route) => json(route, {
    access_token: fakeAccessToken(),
    token_type: 'bearer',
    user: authenticatedUser,
  }));

  await page.goto('/investir');
  await expect(page).toHaveURL(/\/login$/);
  await expect(page.getByText('Entre para acessar a central de decisão.')).toBeVisible();

  await page.getByLabel('E-mail').fill('fase34@fixture.local');
  await page.getByLabel('Senha').fill('fixture-segura-34');
  await page.getByRole('button', { name: 'Entrar', exact: true }).click();

  await expect(page).toHaveURL(/\/investir$/);
  await expect(page.getByRole('heading', { name: 'Central de decisão de investimentos' })).toBeVisible();
});

test('sessão autenticada suporta consulta, reload e logout', async ({ page }) => {
  let budgetRequests = 0;
  let meRequests = 0;
  let capturedBudgetRequest: Request | undefined;
  const token = await seedSession(page);
  await mockMe(page, 200, () => { meRequests += 1; });
  await mockBudget(page, completeBudgetResponse, (request) => {
    budgetRequests += 1;
    capturedBudgetRequest = request;
  });

  await page.goto('/investir');
  await expect(page.getByText('Pronto para analisar')).toBeVisible();
  await expect.poll(() => meRequests).toBe(1);
  await page.getByRole('button', { name: 'Analisar orçamento' }).click();
  await expect(page.getByRole('heading', { name: 'GARE11' })).toBeVisible();
  await expect(page.getByText('Comprar').first()).toBeVisible();
  expect(budgetRequests).toBe(1);
  expect(capturedBudgetRequest?.method()).toBe('GET');
  expect(capturedBudgetRequest?.headers().authorization).toBe(`Bearer ${token}`);
  const budgetUrl = new URL(capturedBudgetRequest?.url() ?? 'http://invalid.local');
  expect(budgetUrl.searchParams.get('budget')).toBe('300');
  expect(budgetUrl.searchParams.get('market')).toBe('FII');
  expect(budgetUrl.searchParams.get('profile')).toBe('CONSERVATIVE');
  expect(budgetUrl.searchParams.get('limit')).toBe('20');
  expect(budgetUrl.searchParams.get('include_warnings')).toBe('false');
  expect(budgetUrl.searchParams.get('explain')).toBe('true');

  await page.reload();
  await expect(page).toHaveURL(/\/investir$/);
  await expect(page.getByRole('heading', { name: 'Central de decisão de investimentos' })).toBeVisible();
  await expect.poll(() => meRequests).toBe(2);

  await page.getByRole('button', { name: /Sair/ }).click();
  await expect(page).toHaveURL(/\/login$/);
  await expect.poll(() => page.evaluate(() => window.localStorage.getItem('vinance_access_token'))).toBeNull();
});

test('token inválido nunca expõe a central nem chama budget-advisor', async ({ page }) => {
  let budgetRequests = 0;
  await seedSession(page);
  await mockMe(page, 401);
  await mockBudget(page, completeBudgetResponse, () => { budgetRequests += 1; });

  await page.goto('/investir');
  await expect(page).toHaveURL(/\/login$/);
  await expect(page.getByText('Sua sessão não é mais válida. Entre novamente para continuar.')).toBeVisible();
  expect(budgetRequests).toBe(0);
  await expect(page.getByRole('heading', { name: 'Central de decisão de investimentos' })).toHaveCount(0);
  await expect(page.getByRole('button', { name: 'Analisar orçamento' })).toHaveCount(0);
  await expect.poll(() => page.evaluate(() => window.localStorage.getItem('vinance_access_token'))).toBeNull();
});

test('JWT expirado redireciona antes de consultar /me', async ({ page }) => {
  let meRequests = 0;
  await seedSession(page, Date.now() - 60_000);
  await page.route('**/api/v1/me', async (route) => {
    if (route.request().method() !== 'OPTIONS') meRequests += 1;
    await json(route, authenticatedUser);
  });

  await page.goto('/investir');
  await expect(page).toHaveURL(/\/login$/);
  await expect(page.getByText('Sua sessão expirou. Entre novamente para continuar.')).toBeVisible();
  expect(meRequests).toBe(0);
});

test('sessão expira enquanto /investir está aberta', async ({ page }) => {
  await seedSession(page, Date.now() + 6_000);
  await mockMe(page);

  await page.goto('/investir');
  await expect(page.getByRole('heading', { name: 'Central de decisão de investimentos' })).toBeVisible();
  await expect(page).toHaveURL(/\/login$/, { timeout: 12_000 });
  await expect(page.getByText('Sua sessão expirou. Entre novamente para continuar.')).toBeVisible();
});

test('layout completo não cria overflow em desktop ou mobile', async ({ page }) => {
  await seedSession(page);
  await mockMe(page);
  await mockBudget(page, longContentResponse);
  await page.goto('/investir');
  await page.getByRole('button', { name: 'Analisar orçamento' }).click();
  await expect(page.getByText('TICKER-EXTREMAMENTE-LONGO-SEM-ESPACOS-1234567890')).toBeVisible();

  for (const viewport of [{ width: 1440, height: 1000 }, { width: 390, height: 844 }, { width: 320, height: 720 }]) {
    await page.setViewportSize(viewport);
    const overflow = await page.evaluate(() => ({
      documentOverflow: document.documentElement.scrollWidth - document.documentElement.clientWidth,
      cardsOutsideViewport: Array.from(document.querySelectorAll<HTMLElement>('.vn-card'))
        .map((card) => ({ className: card.className, rect: card.getBoundingClientRect() }))
        .filter(({ rect }) => rect.left < -1 || rect.right > document.documentElement.clientWidth + 1)
        .map(({ className, rect }) => ({ className, left: rect.left, right: rect.right })),
    }));
    expect(overflow.documentOverflow, JSON.stringify({ viewport, overflow })).toBeLessThanOrEqual(0);
    expect(overflow.cardsOutsideViewport, JSON.stringify({ viewport, overflow })).toEqual([]);
  }
});

test('decisão autenticada é rastreada até histórico e detalhe, e logout volta a bloquear', async ({ page }) => {
  await seedSession(page);
  await mockMe(page);
  let decisionId = '';
  let correlationId = '';

  await page.route('**/api/intelligence/budget-advisor**', async (route) => {
    if (route.request().method() === 'OPTIONS') return json(route, {});
    decisionId = route.request().headers()['x-decision-id'] ?? '';
    correlationId = route.request().headers()['x-correlation-id'] ?? '';
    await json(route, {
      ...completeBudgetResponse,
      decision_id: decisionId,
      correlation_id: correlationId,
    });
  });
  await page.route('**/api/v1/investments/decisions?**', async (route) => {
    await json(route, {
      ...decisionHistoryResponse,
      items: decisionHistoryResponse.items.map((item) => ({ ...item, decision_id: decisionId, correlation_id: correlationId })),
    });
  });
  await page.route('**/api/v1/investments/decisions/*', async (route) => {
    await json(route, { ...decisionDetailResponse, decision_id: decisionId, correlation_id: correlationId });
  });

  await page.goto('/investir');
  await page.getByRole('button', { name: 'Analisar orçamento' }).click();
  await expect(page.getByRole('heading', { name: 'GARE11' })).toBeVisible();
  expect(decisionId).toMatch(/^[0-9a-f-]{36}$/);
  expect(correlationId).toMatch(/^[0-9a-f-]{36}$/);

  await page.getByRole('button', { name: 'Ver histórico' }).click();
  const historyItem = page.getByRole('button', { name: /GARE11/ });
  await expect(historyItem).toContainText('Comprar');
  await historyItem.click();
  await expect(page.getByText('Snapshot imutável')).toBeVisible();
  const decisionDetail = page.locator('aside.vn-history-detail');
  await decisionDetail.getByText('Rastreabilidade completa').click();
  await expect(decisionDetail.getByText(decisionId)).toBeVisible();
  await expect(decisionDetail.getByText(correlationId)).toBeVisible();
  await expect(decisionDetail.getByText('R$ 296,28')).toBeVisible();

  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  expect(overflow).toBeLessThanOrEqual(0);

  await page.getByRole('button', { name: /Sair/ }).click();
  await expect(page).toHaveURL(/\/login$/);
  await page.goto('/investir');
  await expect(page).toHaveURL(/\/login$/);
});
