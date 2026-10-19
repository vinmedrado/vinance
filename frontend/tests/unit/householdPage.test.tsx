import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, expect, test, vi } from 'vitest';

import { HouseholdPage } from '../../src/pages/HouseholdPage';
import { clearSession, setSession } from '../../src/services/api';

const householdService = vi.hoisted(() => ({
  listHouseholds: vi.fn(),
  getDefaultHousehold: vi.fn(),
  createHousehold: vi.fn(),
  listMembers: vi.fn(),
  updateMemberRole: vi.fn(),
  removeMember: vi.fn(),
  leaveHousehold: vi.fn(),
  setDefaultHousehold: vi.fn(),
  listHouseholdInvitations: vi.fn(),
  listIncomingInvitations: vi.fn(),
  createInvitation: vi.fn(),
  cancelInvitation: vi.fn(),
  acceptInvitation: vi.fn(),
  declineInvitation: vi.fn(),
}));

const authService = vi.hoisted(() => ({
  getMe: vi.fn(),
  login: vi.fn(),
  register: vi.fn(),
  logout: vi.fn(),
}));

vi.mock('../../src/features/household/services/household.service', () => householdService);
vi.mock('../../src/features/auth/services/auth.service', () => authService);

const personal = {
  id: 1, name: 'Meu espaço', household_type: 'PERSONAL' as const, created_by_user_id: 10,
  status: 'ACTIVE' as const, created_at: '2026-10-06T12:00:00Z', updated_at: '2026-10-06T12:00:00Z',
};
const shared = { ...personal, id: 2, name: 'Casa Medrado', household_type: 'SHARED' as const };
const owner = {
  id: 20, household_id: 2, user_id: 10, role: 'OWNER' as const, status: 'ACTIVE' as const,
  is_default: false, joined_at: '2026-10-06T12:00:00Z', updated_at: '2026-10-06T12:00:00Z',
  email: 'owner@example.com', full_name: 'Owner',
};

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(<QueryClientProvider client={client}><HouseholdPage /></QueryClientProvider>);
}

beforeEach(() => {
  clearSession();
  setSession('test-token', { id: 10, email: 'owner@example.com', full_name: 'Owner', is_active: true });
  authService.getMe.mockResolvedValue({ id: 10, email: 'owner@example.com', full_name: 'Owner', is_active: true });
  householdService.listHouseholds.mockResolvedValue([personal, shared]);
  householdService.getDefaultHousehold.mockResolvedValue(personal);
  householdService.listIncomingInvitations.mockResolvedValue([]);
  householdService.listMembers.mockImplementation(async (id: number) => id === 2 ? [owner] : [{ ...owner, id: 11, household_id: 1, is_default: true }]);
  householdService.listHouseholdInvitations.mockResolvedValue([]);
  householdService.createHousehold.mockResolvedValue(shared);
  householdService.createInvitation.mockResolvedValue({ id: 99, household_id: 2, household_name: shared.name, invited_email_normalized: 'spouse@example.com', invited_user_id: null, invited_by_user_id: 10, invited_by_name: 'Owner', role: 'MEMBER', status: 'PENDING', expires_at: null, accepted_at: null, declined_at: null, cancelled_at: null, created_at: '2026-10-06T12:00:00Z', updated_at: '2026-10-06T12:00:00Z' });
});

test('personal household never exposes invitation controls', async () => {
  renderPage();
  expect(await screen.findByText('Meu espaço')).toBeInTheDocument();
  expect(screen.getByText('Este espaço aceita somente você e não pode receber convites.')).toBeInTheDocument();
  expect(screen.queryByRole('button', { name: 'Criar convite' })).not.toBeInTheDocument();
});

test('owner creates a pending invitation instead of activating a member', async () => {
  const user = userEvent.setup();
  renderPage();
  await user.selectOptions(await screen.findByLabelText('Casa atual'), '2');
  await screen.findByRole('button', { name: 'Criar convite' });
  await user.type(screen.getByLabelText('E-mail'), 'spouse@example.com');
  await user.click(screen.getByRole('button', { name: 'Criar convite' }));
  await waitFor(() => expect(householdService.createInvitation).toHaveBeenCalledWith(2, {
    email: 'spouse@example.com',
    role: 'MEMBER',
  }));
  expect(householdService.updateMemberRole).not.toHaveBeenCalled();
});

test('dirty administrative form requires explicit discard before switching household', async () => {
  const user = userEvent.setup();
  renderPage();
  await user.type(await screen.findByLabelText('Nome da casa'), 'Novo household');
  await user.selectOptions(screen.getByLabelText('Casa atual'), '2');
  expect(await screen.findByRole('dialog', { name: 'Alterações não salvas' })).toBeInTheDocument();
  expect(screen.getByLabelText('Casa atual')).toHaveValue('1');
  await user.click(screen.getByRole('button', { name: 'Descartar e trocar' }));
  expect(screen.getByLabelText('Casa atual')).toHaveValue('2');
  expect(screen.getByLabelText('Nome da casa')).toHaveValue('');
});
