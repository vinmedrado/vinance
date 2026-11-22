import { expect, test, type Page, type Route } from '@playwright/test';
import { mockBrowserSession } from '../fixtures/authSessionFixture';

// Production registers a service worker, and Playwright cannot route requests
// that the worker has already intercepted. Block it in this mocked-API suite;
// the manifest and service-worker cache policy have dedicated contract tests.
test.use({ serviceWorkers: 'block' });

const headers = {
  'access-control-allow-origin': 'http://127.0.0.1:4173',
  'access-control-allow-headers': 'authorization,content-type',
  'access-control-allow-methods': 'GET,POST,PATCH,DELETE,OPTIONS',
};

const user = {
  id: 9029,
  email: 'access-pwa@fixture.local',
  full_name: 'Pessoa PWA',
  is_active: true,
};

function accessToken() {
  const payload = Buffer.from(JSON.stringify({ sub: user.email, exp: Math.floor(Date.now() / 1000) + 3600 })).toString('base64url');
  return `access.${payload}.signature`;
}

async function json(route: Route, body: unknown, status = 200) {
  if (route.request().method() === 'OPTIONS') return route.fulfill({ status: 204, headers });
  return route.fulfill({ status, headers, contentType: 'application/json', body: JSON.stringify(body) });
}

async function capabilities(page: Page, bootstrapAvailable = true) {
  await page.route('**/api/v1/access/capabilities', (route) => json(route, {
    access_mode: 'INVITE_ONLY',
    public_signup: false,
    bootstrap_available: bootstrapAvailable,
    invite_only: true,
    email_delivery_available: false,
    password_recovery_delivery_available: false,
    cloudflare_access_automation_available: false,
  }));
}

test('login permanece invite-only e bootstrap envia a credencial somente no body', async ({ page }) => {
  await capabilities(page);
  await page.goto('/login');

  await expect(page.getByRole('link', { name: 'Tenho um convite' })).toBeVisible();
  await expect(page.getByRole('link', { name: 'Recuperar acesso' })).toBeVisible();
  await expect(page.getByRole('link', { name: 'Configurar primeira conta' })).toBeVisible();
  await expect(page.getByText('Criar nova conta')).toHaveCount(0);

  let submitted: Record<string, unknown> | undefined;
  await page.route('**/api/v1/access/bootstrap', async (route) => {
    submitted = route.request().postDataJSON() as Record<string, unknown>;
    expect(route.request().url()).not.toContain('credencial-teste');
    await json(route, { access_token: accessToken(), token_type: 'bearer', user }, 201);
  });
  await page.getByRole('link', { name: 'Configurar primeira conta' }).click();
  await page.getByLabel('Nome completo').fill('Pessoa PWA');
  await page.getByLabel('E-mail').fill(user.email);
  await page.getByLabel('Senha', { exact: true }).fill('senha-segura-para-teste');
  await page.getByLabel('Confirmar senha').fill('senha-segura-para-teste');
  await page.getByLabel('Credencial inicial').fill('credencial-teste');
  await page.getByRole('checkbox').check();
  await page.getByRole('button', { name: 'Criar conta administrativa' }).click();

  await expect.poll(() => submitted?.bootstrap_credential).toBe('credencial-teste');
  await expect(page).toHaveURL(/\/dashboard$/);
});

test('configurações PWA são explícitas, responsivas e não pedem permissão no carregamento', async ({ page }) => {
  await mockBrowserSession(page, { token: accessToken(), user, headers });
  await page.route('**/api/v1/me', (route) => json(route, user));
  await page.route('**/api/v1/access/profile', (route) => json(route, { is_platform_admin: false }));
  await page.route('**/api/v1/notifications/preferences', (route) => json(route, {
    push_enabled: false,
    account_events_enabled: true,
    household_invites_enabled: true,
    financial_alerts_enabled: true,
    analysis_updates_enabled: true,
  }));

  await page.goto('/account/settings');
  await expect(page.getByRole('heading', { name: 'Configurações' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Ativar notificações' })).toBeVisible();
  await expect(page.getByText('Permissão', { exact: true })).toBeVisible();

  for (const width of [375, 390, 393, 414, 430]) {
    await page.setViewportSize({ width, height: 844 });
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
    expect(overflow, `overflow em ${width}px`).toBeLessThanOrEqual(0);
  }
});

test('manifesto é servido com escopo e ícones instaláveis', async ({ request }) => {
  const response = await request.get('/manifest.webmanifest');
  expect(response.ok()).toBeTruthy();
  const manifest = await response.json();
  expect(manifest).toMatchObject({ id: '/', start_url: '/dashboard', scope: '/', display: 'standalone' });
  expect(manifest.icons).toEqual(expect.arrayContaining([
    expect.objectContaining({ sizes: '192x192' }),
    expect.objectContaining({ sizes: '512x512' }),
    expect.objectContaining({ purpose: 'maskable' }),
  ]));
});
