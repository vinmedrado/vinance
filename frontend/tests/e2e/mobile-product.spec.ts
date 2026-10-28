import { expect, test, type Page, type Route } from '@playwright/test';

const headers = {
  'access-control-allow-origin': 'http://127.0.0.1:4173',
  'access-control-allow-headers': 'authorization,content-type',
  'access-control-allow-methods': 'GET,POST,PATCH,DELETE,OPTIONS',
};

const user = {
  id: 118,
  email: 'mobile-product@fixture.local',
  full_name: 'Usuário Mobile',
  is_active: true,
};

const household = {
  id: 1180,
  name: 'Casa Mobile',
  household_type: 'SHARED',
  created_by_user_id: user.id,
  status: 'ACTIVE',
  is_default: true,
  created_at: '2026-10-18T10:00:00Z',
  updated_at: '2026-10-18T10:00:00Z',
};

const profile = {
  id: 118,
  user_id: user.id,
  monthly_salary: '8750.00',
  emergency_reserve: '12500.00',
  has_debt_default: false,
  risk_profile: 'moderate',
  investment_horizon_months: 60,
  created_at: '2026-10-18T10:00:00Z',
  updated_at: '2026-10-18T10:00:00Z',
};

const diagnosis = {
  monthly_salary: '8750.00',
  total_expenses_30d: '5100.00',
  emergency_reserve: '12500.00',
  has_debt_default: false,
  risk_profile: 'moderate',
  score: {
    score: 78,
    level: 'GOOD',
    penalties: [],
    recommendations: ['Mantenha as despesas recorrentes atualizadas.'],
  },
  budget: {
    method: 'canonical',
    committed_ratio: '0.5829',
    total_expenses_30d: '5100.00',
    investment_percentage: '0.15',
    investment_capacity: '1312.50',
    emergency_reserve_priority: false,
    high_risk_allowed: false,
    explanation: 'Capacidade calculada com os dados informados.',
  },
};

const recommendations = {
  financial_score: 78,
  investment_capacity: '1312.50',
  adjusted_risk_profile: 'moderate',
  allocation: [
    { asset_class: 'renda_fixa', percentage: '70', amount: '918.75' },
    { asset_class: 'etf', percentage: '30', amount: '393.75' },
  ],
  recommendations_by_class: [],
  warnings: ['CONFIDENCE_BELOW_POLICY_MINIMUM'],
  methodology: ['financial-policy-v1'],
};

const fundamentals = {
  fii: [
    { id: 1, ticker: 'XPML11', price: '104.21', dy_12m: '10.54', p_vp: '0.98', liquidez_diaria: '8421000', source: 'INVESTIDOR10', date: '2026-10-17' },
    { id: 2, ticker: 'XPLG11', price: '97.88', dy_12m: '9.72', p_vp: '0.91', liquidez_diaria: '4321000', source: 'INVESTIDOR10', date: '2026-10-17' },
  ],
  acoes: [
    { id: 3, ticker: 'PETR4', price: '39.15', pl: '5.8', dy_12m: '13.75', liquidez_diaria: '27821014', source: 'INVESTIDOR10', date: '2026-10-17' },
  ],
  etf: [
    { id: 4, ticker: 'BOVA11', price: '142.55', retorno_12m: '12.4', liquidez_diaria: '110000000', source: 'INVESTIDOR10', date: '2026-10-17' },
  ],
  bdr: [
    { id: 5, ticker: 'AAPL34', price: '83.12', retorno_12m: '8.9', volume_medio_diario_brl: '1875000', source: 'INVESTIDOR10', date: '2026-10-17' },
  ],
  cripto: [
    {
      id: 6,
      ticker: 'BITCOIN-TICKER-LONGO-PARA-REGRESSAO-DE-LARGURA',
      price_brl: '365432.123456',
      price_change_24h_pct: '0.050788',
      market_cap_usd: '1278210140000.000000',
      volume_24h_usd: '4827821014.000000',
      source: 'COINGECKO',
      date: '2026-10-18',
    },
  ],
} as const;

function accessToken() {
  const payload = Buffer.from(JSON.stringify({ sub: user.email, exp: Math.floor(Date.now() / 1000) + 3600 })).toString('base64url');
  return `mobile.${payload}.signature`;
}

async function reply(route: Route, body: unknown, status = 200) {
  if (route.request().method() === 'OPTIONS') return route.fulfill({ status: 204, headers });
  return route.fulfill({ status, headers, contentType: 'application/json', body: JSON.stringify(body) });
}

async function installApiFixture(page: Page) {
  await page.route('**/api/**', async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname.replace(/^\/api\/v1/, '');
    const method = request.method();

    if (path === '/refresh') return reply(route, { access_token: accessToken(), token_type: 'bearer', user });
    if (path === '/me') return reply(route, user);
    if (path === '/logout') return route.fulfill({ status: 204, headers });
    if (path === '/financial/households/default') return reply(route, household);
    if (path === '/financial/households' && method === 'GET') return reply(route, [household]);
    if (path === `/financial/households/${household.id}/members`) return reply(route, [{
      id: 1,
      household_id: household.id,
      user_id: user.id,
      role: 'OWNER',
      status: 'ACTIVE',
      is_default: true,
      joined_at: '2026-10-18T10:00:00Z',
      updated_at: '2026-10-18T10:00:00Z',
      email: user.email,
      full_name: user.full_name,
    }]);
    if (path.includes('/invitations')) return reply(route, []);
    if (/\/financial\/households\/\d+\/(?:incomes|expenses|debts|assets|goals)$/.test(path)) return reply(route, []);
    if (path === '/financial/profile') return reply(route, profile);
    if (path === '/financial/diagnosis') return reply(route, diagnosis);
    if (path === '/intelligence/recommendations') return reply(route, recommendations);
    if (path === '/market/macro') return reply(route, { items: [
      { id: 1, code: 'CDI', name: 'CDI', value: '13.75', reference_date: '2026-10-17', source: 'BCB' },
      { id: 2, code: 'SELIC', name: 'Meta Selic', value: '13.75', reference_date: '2026-11-04', source: 'BCB' },
    ], total: 2 });
    if (path === '/market/renda-fixa') return reply(route, { items: [{
      id: 1,
      source_product_id: 'tesouro-selic-2029',
      nome: 'Tesouro Selic 2029',
      indexador: 'SELIC',
      purchase_rate: '0.050788',
      minimum_investment: '151.23',
      liquidity_type: 'DAILY_REPURCHASE',
      maturity_date: '2029-03-01',
      source: 'TESOURO_TRANSPARENTE',
    }], total: 1 });
    if (path === '/trading/overview') return reply(route, {
      paper_only: true,
      product_status: 'NOT_PAPER_READY',
      risk_budget: {
        paper_only: true,
        real_trading_allowed: false,
        real_trading_capital: '0',
        paper_simulation_allowed: true,
        financial_status: 'BLOCKED',
        risk_budget_status: 'DATA_BLOCKED',
        protected_capital: '12500',
        speculative_capital: '0',
        blocking_reasons: ['REAL_TRADING_NOT_SUPPORTED', 'TRADING_DISPATCH_DISABLED'],
        context_fingerprints: {},
        household_id: household.id,
        simulation_rules: { quote_asset: 'USDT' },
      },
      paper_account: null,
      counts: { opportunities: 0, open_positions: 0, pending_orders: 0 },
      performance: { realized_pnl: '0', unrealized_pnl: '0', max_drawdown: '0' },
      models: { status: 'NOT_PAPER_READY', paper_trading_ready: false },
    });
    if (path === '/trading/opportunities') return reply(route, { items: [], total: 0, limit: 50, offset: 0 });
    if (path === '/trading/paper/orders') return reply(route, { items: [], total: 0, limit: 50, offset: 0 });
    if (path === '/trading/paper/positions') return reply(route, { items: [], total: 0, limit: 50, offset: 0 });
    if (path === '/trading/paper/events') return reply(route, { items: [], total: 0, limit: 100, offset: 0 });
    if (path === '/trading/backtests') return reply(route, { items: [], total: 0, limit: 50, offset: 0 });
    if (path === '/trading/models') return reply(route, { items: [], total: 0, limit: 100, offset: 0 });

    const fundamentalMatch = path.match(/^\/market\/fundamentals\/(fii|acoes|etf|bdr|cripto)$/);
    if (fundamentalMatch) {
      const kind = fundamentalMatch[1] as keyof typeof fundamentals;
      const items = fundamentals[kind];
      return reply(route, {
        items,
        total: items.length,
        asset_total: items.length,
        observation_total: kind === 'cripto' ? 10_719_444 : items.length,
        limit: Number(url.searchParams.get('limit') ?? 20),
        offset: Number(url.searchParams.get('offset') ?? 0),
      });
    }

    if (/\/financial\/households\/\d+\/(?:financial-state|policy|capital-allocation|investment-orchestration|action-plan|continuous-autopilot)/.test(path)) {
      return reply(route, { detail: 'Ainda não há decisão para este household.' }, 404);
    }
    if (path.startsWith('/investments/decisions')) return reply(route, { items: [], page: 1, page_size: 8, total: 0, total_pages: 0 });
    if (path.startsWith('/investments/alerts')) return reply(route, { items: [], page: 1, page_size: 8, total: 0, total_pages: 0, unread_count: 0 });
    if (path.startsWith('/investments/alert-subscriptions')) return reply(route, { items: [], total: 0, active: 0, limit: 20 });
    if (path === '/advisor/chat' && method === 'POST') return reply(route, {
      response: 'Considere primeiro os dados já informados e mantenha sua reserva separada.',
      warnings: ['INVESTMENT_CAPACITY_UNKNOWN'],
      context_used: { financial: true, market: false, memory: false },
    });
    return reply(route, { detail: `Fixture sem resposta para ${method} ${path}` }, 404);
  });
}

async function installTradingLifecycleFixture(page: Page) {
  let orders: Record<string, unknown>[] = [];
  let positions: Record<string, unknown>[] = [];
  let events: Record<string, unknown>[] = [];
  const now = '2026-10-26T10:00:00Z';
  await page.route('**/api/v1/trading/**', async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname.replace(/^\/api\/v1/, '');
    if (path === '/trading/overview') return reply(route, {
      paper_only: true,
      product_status: 'PAPER_READY',
      risk_budget: {
        paper_only: true, real_trading_allowed: false, real_trading_capital: '0',
        paper_simulation_allowed: true, financial_status: 'READY', risk_budget_status: 'PAPER_ONLY',
        protected_capital: '12500', speculative_capital: '0',
        blocking_reasons: ['REAL_TRADING_NOT_SUPPORTED'], context_fingerprints: {},
        household_id: household.id, simulation_rules: { quote_asset: 'USDT' },
      },
      paper_account: {
        id: 1, owner_user_id: user.id, ownership_scope: 'PERSONAL', status: 'ACTIVE', quote_asset: 'USDT',
        initial_virtual_balance: '10000', cash: positions.some((item) => item.status === 'OPEN') ? '9900' : '10000', equity: '10000',
        realized_pnl: '0', unrealized_pnl: '0', peak_equity: '10000', max_drawdown: '0', ruleset_version: 'paper-v2',
        paper_only: true, optimistic_version: 1, created_at: now, updated_at: now,
      },
      counts: { opportunities: 1, open_positions: positions.filter((item) => item.status === 'OPEN').length, pending_orders: 0 },
      performance: { realized_pnl: '0', unrealized_pnl: '0', max_drawdown: '0' },
      models: { status: 'PAPER_READY', paper_trading_ready: true },
    });
    if (path === '/trading/opportunities') return reply(route, { items: [{
      signal_id: 41, symbol: 'BTCUSDT', market: 'CRYPTO', interval: '5m', signal_time: now,
      freshness: 'CURRENT', side: 'BUY_CANDIDATE', confidence: '0.81', score: '0.68',
      reference_price: '68000', stop_price: '67660', target_price: '68680', model_version: 'model-v2',
      feature_version: 'v2', target_version: 'v2', guardrail_status: 'APPROVED', reasons: ['Sinal atual e validado'],
    }], total: 1, limit: 50, offset: 0 });
    if (path === '/trading/paper/orders' && request.method() === 'GET') return reply(route, { items: orders, total: orders.length, limit: 50, offset: 0 });
    if (path === '/trading/paper/orders' && request.method() === 'POST') {
      const order = { id: 71, paper_account_id: 1, owner_user_id: user.id, idempotency_key: 'e2e', signal_id: 41, symbol: 'BTCUSDT', market: 'CRYPTO', interval: '5m', side: 'BUY', order_type: 'MARKET', quantity: '0.00147', notional: '100', reference_price: '68010', limit_price: null, stop_price: '67660', target_price: '68680', fee_paid: '0.1', status: 'FILLED', risk_decision: 'PAPER_APPROVED', paper_only: true, created_at: now, filled_at: now };
      orders = [order];
      positions = [{ id: 91, paper_account_id: 1, owner_user_id: user.id, symbol: 'BTCUSDT', market: 'CRYPTO', interval: '5m', side: 'LONG', status: 'OPEN', quantity: '0.00147', average_entry_price: '68010', current_reference_price: '68010', realized_pnl: '0', unrealized_pnl: '0', stop_price: '67660', target_price: '68680', paper_only: true, opened_at: now, closed_at: null }];
      events = [{ id: 1, event_type: 'PAPER_POSITION_OPENED', symbol: 'BTCUSDT', event_payload: {}, decision_context: {}, risk_context: {}, correlation_id: 'e2e', created_at: now }];
      return reply(route, order, 201);
    }
    if (path === '/trading/paper/positions' && request.method() === 'GET') return reply(route, { items: positions, total: positions.length, limit: 50, offset: 0 });
    if (path === '/trading/paper/positions/91/close' && request.method() === 'POST') {
      positions = positions.map((item) => ({ ...item, status: 'CLOSED', closed_at: now }));
      events = [{ id: 2, event_type: 'PAPER_POSITION_CLOSED', symbol: 'BTCUSDT', event_payload: {}, decision_context: {}, risk_context: {}, correlation_id: 'e2e-close', created_at: now }, ...events];
      return reply(route, positions[0]);
    }
    if (path === '/trading/paper/events') return reply(route, { items: events, total: events.length, limit: 100, offset: 0 });
    if (path === '/trading/backtests') return reply(route, { items: [], total: 0, limit: 50, offset: 0 });
    if (path === '/trading/models') return reply(route, { items: [], total: 0, limit: 100, offset: 0 });
    return reply(route, { detail: `Fixture Trading sem resposta para ${request.method()} ${path}` }, 404);
  });
}

async function assertNoGlobalOverflow(page: Page, context: string) {
  const dimensions = await page.evaluate(() => ({
    scrollWidth: document.documentElement.scrollWidth,
    viewportWidth: window.innerWidth,
  }));
  expect(dimensions.scrollWidth, `${context}: ${JSON.stringify(dimensions)}`).toBeLessThanOrEqual(dimensions.viewportWidth);
}

const viewports = [375, 390, 393, 414, 430];
const pages = [
  ['/dashboard', 'inicio'],
  ['/financial', 'situacao'],
  ['/financial/manage', 'dados-financeiros'],
  ['/household', 'casa-familia'],
  ['/market', 'mercado'],
  ['/intelligence', 'analises'],
  ['/investir', 'investir'],
  ['/advisor', 'assistente'],
  ['/account/security', 'seguranca'],
  ['/trading', 'trading'],
] as const;

test('produto móvel permanece contido nas cinco larguras de referência', async ({ page }, testInfo) => {
  test.setTimeout(180_000);
  await installApiFixture(page);

  for (const width of viewports) {
    await page.setViewportSize({ width, height: 844 });
    for (const [path, slug] of pages) {
      await page.goto(path);
      await expect(page.locator('.vn-page')).toBeVisible();
      await assertNoGlobalOverflow(page, `${width}px ${path}`);
      await page.screenshot({ path: testInfo.outputPath(`${width}-${slug}.png`), fullPage: true });
    }

    await page.goto('/market');
    for (const label of ['FIIs', 'Ações', 'ETFs', 'BDRs', 'Cripto']) {
      await page.getByRole('tab', { name: label, exact: true }).click();
      await expect(page.getByRole('tabpanel')).toBeVisible();
      await assertNoGlobalOverflow(page, `${width}px Mercado/${label}`);
    }
  }
});

test('menu móvel contém foco, bloqueia scroll e devolve foco ao acionador', async ({ page }) => {
  await installApiFixture(page);
  await page.setViewportSize({ width: 375, height: 812 });
  await page.goto('/dashboard');

  const trigger = page.getByRole('button', { name: 'Menu', exact: true });
  await trigger.click();
  const dialog = page.getByRole('dialog', { name: 'Conta' });
  await expect(dialog).toBeVisible();
  await expect(page.locator('body')).toHaveCSS('overflow', 'hidden');
  await expect(dialog.getByRole('button', { name: 'Fechar menu', exact: true })).toBeFocused();

  await page.keyboard.press('Escape');
  await expect(dialog).toBeHidden();
  await expect(trigger).toBeFocused();
  await expect(page.locator('body')).not.toHaveCSS('overflow', 'hidden');
});

test('Cripto, BDR e retorno para Cripto não alteram a largura global', async ({ page }) => {
  await installApiFixture(page);
  await page.setViewportSize({ width: 375, height: 812 });
  await page.goto('/market');

  for (const label of ['Cripto', 'BDRs', 'Cripto']) {
    await page.getByRole('tab', { name: label, exact: true }).click();
    await expect(page.getByRole('tabpanel')).toBeVisible();
    await assertNoGlobalOverflow(page, `regressão Cripto → BDR → Cripto: ${label}`);
  }
  await expect(page.locator('.vn-market-mobile-list').getByText('BITCOIN-TICKER-LONGO-PARA-REGRESSAO-DE-LARGURA')).toBeVisible();
  await expect(page.locator('.vn-bottom-nav')).toBeVisible();
});

test('Trading Paper permanece contido e honesto em todas as áreas móveis', async ({ page }) => {
  await installApiFixture(page);
  await page.setViewportSize({ width: 375, height: 812 });
  await page.goto('/trading');
  await expect(page.getByText('PAPER ONLY')).toBeVisible();
  await expect(page.getByText('Trading real', { exact: true })).toBeVisible();
  for (const tab of ['Resumo', 'Oportunidades', 'Simulação', 'Backtests', 'Modelos', 'Histórico']) {
    await page.getByRole('tab', { name: tab, exact: true }).click();
    await expect(page.getByRole('tabpanel')).toBeVisible();
    await assertNoGlobalOverflow(page, `375px Trading/${tab}`);
  }
});

test('oportunidade validada abre e fecha somente uma posição simulada', async ({ page }) => {
  await installApiFixture(page);
  await installTradingLifecycleFixture(page);
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/trading');
  await page.getByRole('tab', { name: 'Oportunidades', exact: true }).click();
  await expect(page.getByText('BTCUSDT')).toBeVisible();
  await page.getByRole('button', { name: 'Ver e simular' }).click();
  await expect(page.getByRole('dialog', { name: /Simular operação/ })).toContainText('Nenhuma ordem real');
  await page.getByRole('button', { name: 'Simular compra' }).click();
  await page.getByRole('tab', { name: 'Simulação', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Fechar posição simulada' })).toBeVisible();
  await page.getByRole('button', { name: 'Fechar posição simulada' }).click();
  await expect(page.getByText('Fechada')).toBeVisible();
  await assertNoGlobalOverflow(page, '390px lifecycle Paper');
});
