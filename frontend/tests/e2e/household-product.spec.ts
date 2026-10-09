import { expect, test, type BrowserContext, type Page, type Route } from '@playwright/test';

const headers = {
  'access-control-allow-origin': 'http://127.0.0.1:4173',
  'access-control-allow-headers': 'authorization,content-type',
  'access-control-allow-methods': 'GET,POST,PATCH,DELETE,OPTIONS',
};

function token(email: string) {
  const payload = Buffer.from(JSON.stringify({ sub: email, exp: Math.floor(Date.now() / 1000) + 3600 })).toString('base64url');
  return `phase-b.${payload}.signature`;
}

async function reply(route: Route, body: unknown, status = 200) {
  if (route.request().method() === 'OPTIONS') return route.fulfill({ status: 204, headers });
  return route.fulfill({ status, headers, contentType: 'application/json', body: JSON.stringify(body) });
}

test('two accounts create, invite and consent to a shared household', async ({ browser }) => {
  // This scenario intentionally exercises the complete two-account lifecycle.
  test.setTimeout(120_000);
  const users = {
    'a@example.com': { id: 1, email: 'a@example.com', full_name: 'Vinicius', is_active: true },
    'b@example.com': { id: 2, email: 'b@example.com', full_name: 'Esposa', is_active: true },
  };
  const personalA = { id: 10, name: 'Vinicius — pessoal', household_type: 'PERSONAL', created_by_user_id: 1, status: 'ACTIVE', created_at: '2026-10-07T10:00:00Z', updated_at: '2026-10-07T10:00:00Z' };
  const personalB = { ...personalA, id: 20, name: 'Esposa — pessoal', created_by_user_id: 2 };
  let shared: typeof personalA | null = null;
  const memberships = new Map<number, Array<any>>([[10, [{ id: 101, household_id: 10, user_id: 1, role: 'OWNER', status: 'ACTIVE', is_default: true, email: 'a@example.com', full_name: 'Vinicius', joined_at: '', updated_at: '' }]], [20, [{ id: 201, household_id: 20, user_id: 2, role: 'OWNER', status: 'ACTIVE', is_default: true, email: 'b@example.com', full_name: 'Esposa', joined_at: '', updated_at: '' }]]]);
  const invitations: Array<any> = [];
  const defaultHousehold = new Map<number, number>([[1, 10], [2, 20]]);
  let invitationSequence = 400;
  let membershipSequence = 301;

  async function configure(context: BrowserContext, email: keyof typeof users) {
    const page = await context.newPage();
    const accessToken = token(email);
    await page.route('**/api/v1/**', async (route) => {
      const request = route.request();
      const path = new URL(request.url()).pathname.replace('/api/v1', '');
      const user = users[email];
      if (path === '/register' && request.method() === 'POST') {
        return reply(route, { access_token: accessToken, token_type: 'bearer', user }, 201);
      }
      if (path === '/me') return reply(route, user);
      if (path === '/financial/households' && request.method() === 'GET') {
        const result = [personalA, personalB, ...(shared ? [shared] : [])].filter((household) => (memberships.get(household.id) ?? []).some((member) => member.user_id === user.id && member.status === 'ACTIVE'));
        return reply(route, result);
      }
      if (path === '/financial/households/default') {
        const all = [personalA, personalB, ...(shared ? [shared] : [])];
        return reply(route, all.find((item) => item.id === defaultHousehold.get(user.id)) ?? (user.id === 1 ? personalA : personalB));
      }
      if (path === '/financial/household-invitations') return reply(route, invitations.filter((invitation) => invitation.invited_email_normalized === email));
      if (path === '/financial/households' && request.method() === 'POST') {
        const payload = request.postDataJSON();
        shared = { ...personalA, id: 30, name: payload.name, household_type: 'SHARED', created_by_user_id: user.id };
        memberships.set(30, [{ id: 301, household_id: 30, user_id: user.id, role: 'OWNER', status: 'ACTIVE', is_default: false, email: user.email, full_name: user.full_name, joined_at: '', updated_at: '' }]);
        return reply(route, shared, 201);
      }
      const memberMatch = path.match(/^\/financial\/households\/(\d+)\/members$/);
      if (memberMatch && request.method() === 'GET') return reply(route, memberships.get(Number(memberMatch[1])) ?? []);
      const memberMutation = path.match(/^\/financial\/households\/(\d+)\/members\/(\d+)$/);
      if (memberMutation && request.method() === 'PATCH') {
        const householdId = Number(memberMutation[1]);
        const member = (memberships.get(householdId) ?? []).find((item) => item.id === Number(memberMutation[2]));
        if (!member) return reply(route, { detail: 'Recurso financeiro não encontrado' }, 404);
        member.role = request.postDataJSON().role;
        return reply(route, member);
      }
      if (memberMutation && request.method() === 'DELETE') {
        const householdId = Number(memberMutation[1]);
        memberships.set(householdId, (memberships.get(householdId) ?? []).filter((item) => item.id !== Number(memberMutation[2])));
        return route.fulfill({ status: 204, headers });
      }
      const invitationListMatch = path.match(/^\/financial\/households\/(\d+)\/invitations$/);
      if (invitationListMatch && request.method() === 'GET') return reply(route, invitations.filter((invitation) => invitation.household_id === Number(invitationListMatch[1])));
      if (invitationListMatch && request.method() === 'POST') {
        const householdId = Number(invitationListMatch[1]);
        const payload = request.postDataJSON();
        const invitation = { id: ++invitationSequence, household_id: householdId, household_name: shared?.name, invited_email_normalized: payload.email.toLowerCase(), invited_user_id: 2, invited_by_user_id: user.id, invited_by_name: user.full_name, role: payload.role, status: 'PENDING', expires_at: null, accepted_at: null, declined_at: null, cancelled_at: null, created_at: '2026-10-07T10:00:00Z', updated_at: '2026-10-07T10:00:00Z' };
        invitations.push(invitation);
        return reply(route, invitation, 201);
      }
      const cancelMatch = path.match(/^\/financial\/households\/(\d+)\/invitations\/(\d+)\/cancel$/);
      if (cancelMatch && request.method() === 'POST') {
        const invitation = invitations.find((item) => item.id === Number(cancelMatch[2]));
        if (!invitation) return reply(route, { detail: 'Recurso financeiro não encontrado' }, 404);
        invitation.status = 'CANCELLED';
        return reply(route, invitation);
      }
      const acceptMatch = path.match(/^\/financial\/household-invitations\/(\d+)\/accept$/);
      if (acceptMatch && request.method() === 'POST') {
        const invitation = invitations.find((item) => item.id === Number(acceptMatch[1]));
        if (!invitation || invitation.invited_email_normalized !== email) return reply(route, { detail: 'Recurso financeiro não encontrado' }, 404);
        invitation.status = 'ACCEPTED';
        const current = memberships.get(invitation.household_id) ?? [];
        if (!current.some((member) => member.user_id === user.id)) current.push({ id: ++membershipSequence, household_id: invitation.household_id, user_id: user.id, role: invitation.role, status: 'ACTIVE', is_default: false, email: user.email, full_name: user.full_name, joined_at: '', updated_at: '' });
        return reply(route, invitation);
      }
      const declineMatch = path.match(/^\/financial\/household-invitations\/(\d+)\/decline$/);
      if (declineMatch && request.method() === 'POST') {
        const invitation = invitations.find((item) => item.id === Number(declineMatch[1]));
        if (!invitation || invitation.invited_email_normalized !== email) return reply(route, { detail: 'Recurso financeiro não encontrado' }, 404);
        invitation.status = 'DECLINED';
        return reply(route, invitation);
      }
      const defaultMatch = path.match(/^\/financial\/households\/(\d+)\/default$/);
      if (defaultMatch && request.method() === 'POST') {
        defaultHousehold.set(user.id, Number(defaultMatch[1]));
        return reply(route, shared);
      }
      const leaveMatch = path.match(/^\/financial\/households\/(\d+)\/leave$/);
      if (leaveMatch && request.method() === 'POST') {
        const householdId = Number(leaveMatch[1]);
        memberships.set(householdId, (memberships.get(householdId) ?? []).filter((member) => member.user_id !== user.id));
        defaultHousehold.set(user.id, user.id === 1 ? 10 : 20);
        return route.fulfill({ status: 204, headers });
      }
      return reply(route, { detail: `Unhandled ${request.method()} ${path}` }, 404);
    });
    await page.goto('/login');
    await page.getByRole('button', { name: 'Criar nova conta' }).click();
    await page.getByLabel('Nome').fill(users[email].full_name);
    await page.getByLabel('E-mail').fill(email);
    await page.getByLabel('Senha').fill('phase-b-password');
    await page.getByRole('button', { name: 'Registrar e entrar' }).click();
    await expect(page).toHaveURL(/\/dashboard$/);
    await page.goto('/household');
    return page;
  }

  const contextA = await browser.newContext();
  const contextB = await browser.newContext();
  const pageA = await configure(contextA, 'a@example.com');
  const pageB = await configure(contextB, 'b@example.com');

  await pageA.getByLabel('Nome da casa').fill('Casa Medrado');
  await pageA.getByRole('button', { name: 'Criar compartilhado' }).click();
  await expect(pageA.getByText('Household compartilhado criado.')).toBeVisible();
  await pageA.getByLabel('E-mail').fill('b@example.com');
  await pageA.getByRole('button', { name: 'Criar convite' }).click();
  await expect(pageA.getByText('b@example.com')).toBeVisible();
  await pageA.getByRole('button', { name: 'Cancelar convite' }).click();
  await expect(pageA.getByRole('button', { name: 'Cancelar convite' })).toHaveCount(0);

  await pageA.getByLabel('E-mail').fill('b@example.com');
  await pageA.getByRole('button', { name: 'Criar convite' }).click();
  await pageB.reload();
  await pageB.getByRole('button', { name: 'Recusar' }).click();
  await expect(pageB.getByRole('button', { name: 'Aceitar' })).toHaveCount(0);

  await pageA.reload();
  await pageA.getByLabel('Household atual').selectOption('30');
  await pageA.getByLabel('E-mail').fill('b@example.com');
  await pageA.getByRole('button', { name: 'Criar convite' }).click();

  await pageB.reload();
  await expect(pageB.getByText('Casa Medrado')).toBeVisible();
  await pageB.getByRole('button', { name: 'Aceitar' }).click();
  await expect(pageB.getByLabel('Household atual')).toContainText('Casa Medrado');
  await pageB.getByLabel('Household atual').selectOption('30');
  await expect(pageB.getByText('Compartilhado', { exact: true })).toBeVisible();
  await pageB.getByRole('button', { name: 'Definir como padrão' }).click();
  await expect(pageB.getByText('Padrão', { exact: true })).toBeVisible();

  await pageA.reload();
  await pageA.getByLabel('Household atual').selectOption('30');
  await expect(pageA.getByText('Esposa')).toBeVisible();
  const roleUpdated = pageA.waitForResponse((response) => (
    response.request().method() === 'PATCH'
    && /\/financial\/households\/30\/members\/\d+$/.test(new URL(response.url()).pathname)
  ));
  await pageA.getByText('Esposa', { exact: true }).locator('xpath=../..//select').selectOption('OWNER');
  await roleUpdated;
  await pageB.reload();
  await pageB.getByLabel('Household atual').selectOption('30');
  await expect(pageB.getByRole('button', { name: 'Sair do household' })).toBeVisible();
  pageB.once('dialog', (dialog) => dialog.accept());
  await pageB.getByRole('button', { name: 'Sair do household' }).click();
  await expect(pageB.getByLabel('Household atual')).not.toContainText('Casa Medrado');

  await pageA.reload();
  await pageA.getByLabel('Household atual').selectOption('30');
  await pageA.getByLabel('E-mail').fill('b@example.com');
  await pageA.getByRole('button', { name: 'Criar convite' }).click();
  await pageB.reload();
  await pageB.getByRole('button', { name: 'Aceitar' }).click();
  await pageA.reload();
  await pageA.getByLabel('Household atual').selectOption('30');
  pageA.once('dialog', (dialog) => dialog.accept());
  await pageA.getByRole('button', { name: 'Remover' }).click();
  await expect(pageA.getByText('Esposa')).toHaveCount(0);
  expect((memberships.get(30) ?? []).filter((member) => member.user_id === 2)).toHaveLength(0);

  await contextA.close();
  await contextB.close();
});
