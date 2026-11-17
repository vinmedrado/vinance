import { expect, test, type Page, type Route } from '@playwright/test';

const user = {
  id: 701,
  email: 'contexto-financeiro@fixture.local',
  full_name: 'Pessoa de teste',
  is_active: true,
};

const personal = {
  id: 7010,
  name: 'Espaço pessoal',
  household_type: 'PERSONAL',
  created_by_user_id: user.id,
  status: 'ACTIVE',
  created_at: '2026-11-05T10:00:00Z',
  updated_at: '2026-11-05T10:00:00Z',
};

const shared = {
  ...personal,
  id: 7020,
  name: 'Casa de teste',
  household_type: 'SHARED',
};

const headers = {
  'access-control-allow-origin': 'http://127.0.0.1:4173',
  'access-control-allow-headers': 'authorization,content-type,idempotency-key',
  'access-control-allow-methods': 'GET,POST,PATCH,DELETE,OPTIONS',
};

function accessToken() {
  const payload = Buffer.from(JSON.stringify({ sub: user.email, exp: Math.floor(Date.now() / 1000) + 3600 })).toString('base64url');
  return `context.${payload}.signature`;
}

async function reply(route: Route, body: unknown, status = 200) {
  if (route.request().method() === 'OPTIONS') return route.fulfill({ status: 204, headers });
  return route.fulfill({ status, headers, contentType: 'application/json', body: JSON.stringify(body) });
}

async function installFinancialContextFixture(page: Page) {
  let active = personal;
  let personalExpenses = [{
    id: 801,
    household_id: personal.id,
    user_id: user.id,
    ownership_scope: 'PERSONAL',
    description: 'Energia da casa',
    amount: '240.00',
    category: 'moradia',
    due_date: '2026-11-10',
    paid_at: null,
    is_paid: false,
    is_recurring: true,
    expense_nature: 'FIXED',
    created_at: '2026-11-05T10:00:00Z',
    updated_at: '2026-11-05T10:00:00Z',
  }];
  let sharedExpenses: typeof personalExpenses = [];

  await page.route('**/api/**', async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname.replace(/^\/api\/v1/, '');
    const method = request.method();

    if (path === '/refresh') return reply(route, { access_token: accessToken(), token_type: 'bearer', user });
    if (path === '/me') return reply(route, user);
    if (path === '/financial/households' && method === 'GET') return reply(route, [personal, shared]);
    if (path === '/financial/households/default') return reply(route, active);
    if (path === `/financial/households/${personal.id}/default` && method === 'POST') {
      active = personal;
      return reply(route, active);
    }
    if (path === `/financial/households/${shared.id}/default` && method === 'POST') {
      active = shared;
      return reply(route, active);
    }
    if (/\/financial\/households\/\d+\/members$/.test(path)) return reply(route, [{
      id: 1,
      household_id: Number(path.split('/')[3]),
      user_id: user.id,
      role: 'OWNER',
      status: 'ACTIVE',
      is_default: true,
      joined_at: '2026-11-05T10:00:00Z',
      updated_at: '2026-11-05T10:00:00Z',
      email: user.email,
      full_name: user.full_name,
    }]);
    if (path === '/financial/profile') return reply(route, {
      id: 1,
      user_id: user.id,
      monthly_salary: '5000.00',
      emergency_reserve: '0.00',
      has_debt_default: false,
      risk_profile: 'moderate',
      investment_horizon_months: null,
      created_at: '2026-11-05T10:00:00Z',
      updated_at: '2026-11-05T10:00:00Z',
    });

    const expenseList = path.match(/^\/financial\/households\/(\d+)\/expenses$/);
    if (expenseList && method === 'GET') {
      return reply(route, Number(expenseList[1]) === personal.id ? personalExpenses : sharedExpenses);
    }
    if (expenseList && method === 'POST') {
      const payload = request.postDataJSON();
      const householdId = Number(expenseList[1]);
      const created = {
        id: 900 + personalExpenses.length + sharedExpenses.length,
        household_id: householdId,
        user_id: user.id,
        ...payload,
        created_at: '2026-11-05T10:10:00Z',
        updated_at: '2026-11-05T10:10:00Z',
      };
      if (householdId === personal.id) personalExpenses = [...personalExpenses, created];
      else sharedExpenses = [...sharedExpenses, created];
      return reply(route, created);
    }
    if (/\/financial\/households\/\d+\/(?:incomes|debts|assets|goals)$/.test(path)) return reply(route, []);

    if (path === `/financial/households/${shared.id}/expenses/transfer-from-personal/preview`) {
      return reply(route, {
        resource_type: 'EXPENSE',
        target_household_id: shared.id,
        record_count: 1,
        requires_duplicate_review: false,
        items: [{
          record_id: 801,
          source_household_id: personal.id,
          description: 'Energia da casa',
          amount: '240.00',
          effective_date: '2026-11-10',
          possible_duplicates: [],
        }],
      });
    }
    if (path === `/financial/households/${shared.id}/expenses/transfer-from-personal` && method === 'POST') {
      const moved = { ...personalExpenses[0], household_id: shared.id, ownership_scope: 'HOUSEHOLD' };
      personalExpenses = personalExpenses.filter((item) => item.id !== 801);
      sharedExpenses = [...sharedExpenses, moved];
      return reply(route, {
        transfer_id: 1,
        resource_type: 'EXPENSE',
        target_household_id: shared.id,
        record_count: 1,
        moved_record_ids: [801],
        source_household_ids: [personal.id],
        status: 'COMMITTED',
        replayed: false,
        created_at: '2026-11-05T10:15:00Z',
      });
    }
    return reply(route, { detail: `Fixture sem resposta para ${method} ${path}` }, 404);
  });
}

async function assertNoOverflow(page: Page, context: string) {
  const width = await page.evaluate(() => ({
    scroll: document.documentElement.scrollWidth,
    viewport: window.innerWidth,
  }));
  expect(width.scroll, `${context}: ${JSON.stringify(width)}`).toBeLessThanOrEqual(width.viewport);
}

async function assertContextLabelIsReadable(page: Page, expected: string) {
  const indicator = page.locator('.vn-financial-context-switcher__trigger');
  await expect(indicator).toContainText(expected);
  const dimensions = await indicator.evaluate((element) => ({
    client: element.clientWidth,
    scroll: element.scrollWidth,
  }));
  expect(dimensions.scroll, JSON.stringify(dimensions)).toBeLessThanOrEqual(dimensions.client);
}

for (const width of [375, 390, 393, 414, 430]) {
  test(`contexto financeiro e transferência permanecem claros em ${width}px`, async ({ page }, testInfo) => {
    await installFinancialContextFixture(page);
    await page.setViewportSize({ width, height: width === 375 ? 812 : 896 });
    await page.goto('/financial/manage');

    await expect(page.getByText('Registrou alguma despesa da casa em Minhas finanças?')).toBeVisible();
    await assertContextLabelIsReadable(page, 'Minhas finanças');
    await assertNoOverflow(page, `${width}px dados pessoais`);

    const expenseSection = page.locator('[data-financial-resource="expenses"]');
    await expenseSection.getByRole('button', { name: 'Adicionar' }).click();
    const editor = page.getByRole('dialog', { name: 'Adicionar despesa' });
    await expect(editor.getByText('Onde deseja registrar?')).toBeVisible();
    await editor.getByRole('radio', { name: /Finanças do casal/ }).check();
    await editor.getByLabel('Descrição').fill('Internet da casa');
    await editor.getByLabel('Valor').fill('150');
    await editor.getByLabel('Categoria').fill('moradia');
    await editor.getByRole('button', { name: 'Salvar' }).click();
    await expect(page.getByText('Despesa registrada em Finanças do casal.')).toBeVisible();

    await expenseSection.getByRole('button', { name: 'Mover para Finanças do casal' }).click();
    const transfer = page.getByRole('dialog', { name: 'Mover despesa para Finanças do casal' });
    await expect(transfer.getByText(/A transferência é atômica/)).toBeVisible();
    await assertNoOverflow(page, `${width}px prévia de transferência`);
    await page.screenshot({ path: testInfo.outputPath(`${width}-transfer-preview.png`) });
    await transfer.getByRole('button', { name: 'Confirmar transferência' }).click();
    await expect(page.getByText('1 despesa transferida para Finanças do casal.')).toBeVisible();

    const switcher = page.getByRole('button', { name: /Contexto financeiro: Minhas finanças/ });
    await switcher.click();
    await page.getByRole('menuitemradio', { name: /Finanças do casal/ }).click();
    await expect(page.getByText('Este é o espaço financeiro compartilhado.')).toBeVisible();
    await expect(page.getByText(/Suas finanças pessoais continuam privadas/)).toBeVisible();
    await assertContextLabelIsReadable(page, 'Finanças do casal');
    await assertNoOverflow(page, `${width}px contexto compartilhado`);
    await page.evaluate(() => window.scrollTo(0, 0));
    await page.screenshot({ path: testInfo.outputPath(`${width}-shared-context.png`) });
  });
}

test('o seletor de contexto permanece explícito no desktop', async ({ page }, testInfo) => {
  await installFinancialContextFixture(page);
  await page.setViewportSize({ width: 1280, height: 800 });
  await page.goto('/financial/manage');

  await assertContextLabelIsReadable(page, 'Minhas finanças');
  await assertNoOverflow(page, 'desktop 1280px');
  await page.getByRole('button', { name: /Contexto financeiro: Minhas finanças/ }).click();
  await expect(page.getByRole('menu', { name: 'Escolher contexto financeiro' })).toBeVisible();
  await expect(page.getByRole('menuitemradio', { name: /Finanças do casal/ })).toContainText('Casa de teste');
  await page.screenshot({ path: testInfo.outputPath('1280-context-switcher.png') });
});
