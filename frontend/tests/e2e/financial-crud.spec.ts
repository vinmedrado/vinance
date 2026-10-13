import { expect, test, type Page, type Route } from '@playwright/test';
import { mockBrowserSession } from '../fixtures/authSessionFixture';

const headers = {
  'access-control-allow-origin': 'http://127.0.0.1:4173',
  'access-control-allow-headers': 'authorization,content-type',
  'access-control-allow-methods': 'GET,POST,PATCH,DELETE,OPTIONS',
};

const user = { id: 71, email: 'phase-b-owner@example.com', full_name: 'Phase B Owner', is_active: true };
const household = {
  id: 710,
  name: 'Casa Phase B',
  household_type: 'SHARED',
  created_by_user_id: user.id,
  status: 'ACTIVE',
  created_at: '2026-10-07T10:00:00Z',
  updated_at: '2026-10-07T10:00:00Z',
};

function accessToken() {
  const payload = Buffer.from(JSON.stringify({ sub: user.email, exp: Math.floor(Date.now() / 1000) + 3600 })).toString('base64url');
  return `phase-b.${payload}.signature`;
}

async function reply(route: Route, body: unknown, status = 200) {
  if (route.request().method() === 'OPTIONS') return route.fulfill({ status: 204, headers });
  return route.fulfill({ status, headers, contentType: 'application/json', body: JSON.stringify(body) });
}

test('manages the five canonical financial resources and the personal profile', async ({ page }) => {
  test.setTimeout(60_000);
  const records: Record<string, Array<Record<string, unknown>>> = {
    incomes: [], expenses: [], debts: [], assets: [], goals: [],
  };
  let nextId = 1;
  let profile = {
    id: 9,
    user_id: user.id,
    monthly_salary: '5000.00',
    emergency_reserve: '1000.00',
    has_debt_default: false,
    risk_profile: 'moderate',
    created_at: '2026-10-07T10:00:00Z',
    updated_at: '2026-10-07T10:00:00Z',
  };

  await page.route('**/api/v1/**', async (route) => {
    const request = route.request();
    const method = request.method();
    const path = new URL(request.url()).pathname.replace('/api/v1', '');
    if (path === '/me') return reply(route, user);
    if (path === '/financial/households' && method === 'GET') return reply(route, [household]);
    if (path === '/financial/households/default') return reply(route, household);
    if (path === `/financial/households/${household.id}/members`) return reply(route, [{
      id: 1,
      household_id: household.id,
      user_id: user.id,
      role: 'OWNER',
      status: 'ACTIVE',
      is_default: true,
      joined_at: '2026-10-07T10:00:00Z',
      updated_at: '2026-10-07T10:00:00Z',
      email: user.email,
      full_name: user.full_name,
    }]);
    if (path === '/financial/profile' && method === 'GET') return reply(route, profile);
    if (path === '/financial/profile' && method === 'POST') {
      profile = { ...profile, ...request.postDataJSON(), updated_at: '2026-10-07T11:00:00Z' };
      return reply(route, profile);
    }
    const match = path.match(new RegExp(`^/financial/households/${household.id}/(incomes|expenses|debts|assets|goals)(?:/(\\d+))?$`));
    if (match) {
      const [, resource, rawId] = match;
      const collection = records[resource];
      if (!rawId && method === 'GET') return reply(route, collection);
      if (!rawId && method === 'POST') {
        const payload = request.postDataJSON();
        const created = {
          id: nextId++, household_id: household.id, user_id: user.id,
          created_at: '2026-10-07T10:00:00Z', updated_at: '2026-10-07T10:00:00Z',
          ...payload,
        };
        collection.unshift(created);
        return reply(route, created, 201);
      }
      const id = Number(rawId);
      const index = collection.findIndex((item) => item.id === id);
      if (index < 0) return reply(route, { detail: 'Recurso financeiro não encontrado' }, 404);
      if (method === 'PATCH') {
        collection[index] = { ...collection[index], ...request.postDataJSON(), updated_at: '2026-10-07T11:00:00Z' };
        return reply(route, collection[index]);
      }
      if (method === 'DELETE') {
        collection.splice(index, 1);
        return route.fulfill({ status: 204, headers });
      }
    }
    return reply(route, { detail: `Unhandled ${method} ${path}` }, 404);
  });

  await login(page);
  await expect(page.getByRole('heading', { name: 'Gerenciar minha vida financeira' })).toBeVisible();

  await createEditDelete(page, 'Receitas', 'Adicionar receita', async () => {
    await page.getByLabel('Descrição').fill('Salário');
    await page.getByLabel('Valor').fill('5000');
    await page.getByLabel('Tipo de renda').fill('salário');
  }, 'Salário', 'Salário principal');

  await createEditDelete(page, 'Despesas', 'Adicionar despesa', async () => {
    await page.getByLabel('Descrição').fill('Moradia');
    await page.getByLabel('Valor').fill('1200');
    await page.getByLabel('Categoria').fill('casa');
  }, 'Moradia', 'Moradia mensal');

  await createEditDelete(page, 'Dívidas', 'Adicionar dívida', async () => {
    await page.getByLabel('Nome').fill('Financiamento');
    await page.getByLabel('Tipo de dívida').fill('financiamento');
    await page.getByLabel('Saldo atual (opcional)').fill('0');
  }, 'Financiamento', 'Financiamento atualizado', async () => {
    await page.getByLabel('Status').selectOption('PAID');
  });

  await createEditDelete(page, 'Patrimônio', 'Adicionar patrimônio', async () => {
    await page.getByLabel('Nome').fill('Reserva bancária');
    await page.getByLabel('Valor atual (opcional)').fill('2500');
  }, 'Reserva bancária', 'Reserva principal');

  await createEditDelete(page, 'Objetivos', 'Adicionar objetivo', async () => {
    await page.getByLabel('Nome').fill('Viagem');
    await page.getByLabel('Valor alvo').fill('10000');
  }, 'Viagem', 'Viagem em família', async () => {
    await page.getByLabel('Status').selectOption('PAUSED');
  });

  await page.getByRole('button', { name: 'Editar perfil' }).click();
  await page.getByLabel('Reserva de emergência').fill('3500');
  await page.getByRole('button', { name: 'Salvar perfil' }).click();
  await expect(page.getByText('R$ 3.500,00')).toBeVisible();

  expect(records.incomes).toHaveLength(0);
  expect(records.expenses).toHaveLength(0);
  expect(records.debts).toHaveLength(0);
  expect(records.assets).toHaveLength(0);
  expect(records.goals).toHaveLength(0);
  expect(profile.emergency_reserve).toBe(3500);
});

async function login(page: Page) {
  await mockBrowserSession(page, { token: accessToken(), user, headers });
  await page.goto('/financial/manage');
}

async function createEditDelete(
  page: Page,
  sectionTitle: string,
  createDialogTitle: string,
  fillCreate: () => Promise<void>,
  originalName: string,
  updatedName: string,
  fillEdit?: () => Promise<void>,
) {
  const card = page.getByRole('heading', { name: sectionTitle, exact: true }).locator('xpath=ancestor::section[1]');
  await card.getByRole('button', { name: 'Adicionar', exact: true }).click();
  await expect(page.getByRole('dialog', { name: createDialogTitle })).toBeVisible();
  await fillCreate();
  await page.getByRole('button', { name: 'Salvar', exact: true }).click();
  await expect(card.getByText(originalName, { exact: true })).toBeVisible();

  await card.getByRole('button', { name: 'Editar' }).click();
  const nameLabel = sectionTitle === 'Receitas' || sectionTitle === 'Despesas' ? 'Descrição' : 'Nome';
  await page.getByLabel(nameLabel).fill(updatedName);
  if (fillEdit) await fillEdit();
  await page.getByRole('button', { name: 'Salvar', exact: true }).click();
  await expect(card.getByText(updatedName, { exact: true })).toBeVisible();

  page.once('dialog', (dialog) => dialog.accept());
  await card.getByRole('button', { name: 'Excluir' }).click();
  await expect(card.getByText(updatedName, { exact: true })).toHaveCount(0);
}
