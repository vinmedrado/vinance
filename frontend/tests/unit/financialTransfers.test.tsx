import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, expect, test, vi } from 'vitest';
import { TransferFinancialRecordsDialog } from '../../src/features/financial-state/components/TransferFinancialRecordsDialog';

const service = vi.hoisted(() => ({
  previewFinancialRecordTransfer: vi.fn(),
  commitFinancialRecordTransfer: vi.fn(),
}));

vi.mock('../../src/features/financial-state/services/financialState.service', async (loadOriginal) => ({
  ...(await loadOriginal<Record<string, unknown>>()),
  ...service,
}));

vi.mock('../../src/features/auth/hooks/useAuth', () => ({
  useSessionToken: () => 'session-a',
}));

const household = {
  id: 20,
  name: 'Casa Silva',
  household_type: 'SHARED' as const,
  created_by_user_id: 1,
  status: 'ACTIVE' as const,
  created_at: '2026-11-04T00:00:00Z',
  updated_at: '2026-11-04T00:00:00Z',
};

function renderDialog(onTransferred = vi.fn()) {
  const client = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <TransferFinancialRecordsDialog
        open
        resource="expenses"
        recordIds={[7, 8]}
        targetHousehold={household}
        onClose={vi.fn()}
        onTransferred={onTransferred}
      />
    </QueryClientProvider>,
  );
  return { client, onTransferred };
}

beforeEach(() => {
  service.previewFinancialRecordTransfer.mockReset();
  service.commitFinancialRecordTransfer.mockReset();
  service.previewFinancialRecordTransfer.mockResolvedValue({
    resource_type: 'EXPENSE',
    target_household_id: 20,
    record_count: 2,
    requires_duplicate_review: true,
    items: [
      {
        record_id: 7,
        source_household_id: 10,
        description: 'Mercado',
        amount: '250.00',
        effective_date: '2026-11-03',
        possible_duplicates: [{ candidate_id: 90, description: 'Mercado', amount: '250.00', effective_date: '2026-11-03' }],
      },
      {
        record_id: 8,
        source_household_id: 10,
        description: 'Internet',
        amount: '120.00',
        effective_date: '2026-11-04',
        possible_duplicates: [],
      },
    ],
  });
  service.commitFinancialRecordTransfer.mockResolvedValue({
    transfer_id: 4,
    resource_type: 'EXPENSE',
    target_household_id: 20,
    record_count: 2,
    moved_record_ids: [7, 8],
    source_household_ids: [10],
    status: 'COMMITTED',
    replayed: false,
    created_at: '2026-11-04T12:00:00Z',
  });
});
test('shows an atomic preview and requires explicit duplicate review', async () => {
  const user = userEvent.setup();
  const { client, onTransferred } = renderDialog();
  const invalidateQueries = vi.spyOn(client, 'invalidateQueries');

  expect(await screen.findByText('Mercado')).toBeInTheDocument();
  expect(screen.getByText(/se um item falhar, nenhum será movido/i)).toBeInTheDocument();
  expect(screen.getByText(/Possível lançamento semelhante/i)).toBeInTheDocument();
  expect(screen.getByRole('list', { name: 'Lançamentos semelhantes para revisão' })).toHaveTextContent('03/11/2026');
  expect(screen.getByRole('list', { name: 'Lançamentos semelhantes para revisão' })).toHaveTextContent('R$ 250,00');
  const confirm = screen.getByRole('button', { name: 'Confirmar transferência' });
  expect(confirm).toBeDisabled();

  await user.click(screen.getByRole('checkbox', { name: /Revisei os possíveis/i }));
  await user.click(confirm);

  await waitFor(() => expect(service.commitFinancialRecordTransfer).toHaveBeenCalledWith(
    'expenses', 20, [7, 8], true, expect.stringMatching(/^financial-transfer-expenses-/),
  ));
  expect(onTransferred).toHaveBeenCalledWith(2);
  for (const householdId of [10, 20]) {
    for (const queryKey of [
      ['financial-state', 'session-a', 'expenses', householdId],
      ['financial-state', 'session-a', 'current', householdId],
      ['financial-policy', 'session-a', 'current', householdId],
      ['capital-allocation', 'session-a', 'current', householdId],
      ['investment-orchestration', 'session-a', 'current', householdId],
      ['action-plan', 'session-a', 'current', householdId],
      ['continuous-autopilot', 'session-a', 'current', householdId],
    ]) {
      expect(invalidateQueries).toHaveBeenCalledWith({ queryKey });
    }
  }
});
