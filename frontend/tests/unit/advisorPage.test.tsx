import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, test, vi } from 'vitest';
import { AdvisorPage } from '../../src/pages/AdvisorPage';

const mocks = vi.hoisted(() => ({ chat: vi.fn(), profile: vi.fn() }));

vi.mock('../../src/features/advisor/hooks/useAdvisorChat', () => ({ useAdvisorChat: () => mocks.chat() }));
vi.mock('../../src/features/financial/hooks/useFinancial', () => ({ useFinancialProfile: () => mocks.profile() }));

beforeEach(() => {
  mocks.profile.mockReturnValue({ data: { id: 1 }, error: null });
  mocks.chat.mockReturnValue({
    isPending: false,
    error: null,
    mutateAsync: vi.fn(async () => ({
      response: 'Sua reserva merece atenção antes de aumentar o risco.',
      warnings: [{ code: 'context_limited', message: 'Contexto incompleto.' }],
      context_used: { financial: true, market: false, memory: false },
    })),
  });
});

describe('Assistente financeiro', () => {
  test('usa nomenclatura honesta e mostra o contexto confirmado pela API', async () => {
    render(<AdvisorPage />);

    expect(screen.getByRole('heading', { name: 'Entenda melhor suas decisões' })).toBeInTheDocument();
    expect(screen.queryByText('Advisor IA')).not.toBeInTheDocument();

    const input = screen.getByPlaceholderText(/Pergunte sobre sua situação/);
    await userEvent.type(input, 'Como está minha reserva?');
    await userEvent.click(screen.getByRole('button', { name: 'Enviar' }));

    expect(await screen.findByText('Sua reserva merece atenção antes de aumentar o risco.')).toBeInTheDocument();
    expect(screen.getByText('Situação financeira considerada')).toBeInTheDocument();
    expect(screen.getByText(/contexto financeiro incompleto/i)).toBeInTheDocument();
    expect(screen.queryByText(/confiança: /i)).not.toBeInTheDocument();
  });
});
