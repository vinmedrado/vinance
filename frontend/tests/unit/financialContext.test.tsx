import { useEffect } from 'react';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, test, vi } from 'vitest';
import {
  FinancialContextProvider,
  financialContextCopy,
  normalizeHousehold,
  normalizeHouseholds,
  useFinancialContext,
} from '../../src/features/household/context/FinancialContextProvider';
import { FinancialContextSwitcher } from '../../src/features/household/components/FinancialContextSwitcher';

const hooks = vi.hoisted(() => ({
  mutateAsync: vi.fn(),
  list: [
    { id: 10, name: 'Pessoal', household_type: 'PERSONAL', status: 'ACTIVE' },
    { id: 20, name: 'Casa Silva', household_type: 'SHARED', status: 'ACTIVE' },
  ],
  active: { id: 20, name: 'Casa Silva', household_type: 'SHARED', status: 'ACTIVE' },
}));

vi.mock('../../src/features/household/hooks/useHousehold', () => ({
  useHouseholdList: () => ({ data: hooks.list, isLoading: false, error: null }),
  useHouseholdDefault: () => ({ data: hooks.active, isLoading: false, error: null }),
  useSetDefaultHousehold: () => ({ mutateAsync: hooks.mutateAsync, isPending: false, error: null }),
}));

vi.mock('../../src/features/auth/hooks/useAuth', () => ({
  useSessionToken: () => 'session-a',
}));

function Probe({ dirty = false, onDiscard = vi.fn() }: { dirty?: boolean; onDiscard?: () => void }) {
  const context = useFinancialContext();
  useEffect(() => context.registerSwitchGuard({
    isDirty: () => dirty,
    discard: onDiscard,
  }), [context.registerSwitchGuard, dirty, onDiscard]);
  return (
    <div>
      <span>{context.label}</span>
      <span>{context.description}</span>
      <button type="button" onClick={() => context.switchContext(10)}>Mudar para pessoal</button>
    </div>
  );
}

beforeEach(() => {
  hooks.mutateAsync.mockReset();
  hooks.mutateAsync.mockResolvedValue(hooks.list[0]);
});
describe('contexto financeiro global', () => {
  test('falha fechado quando a API devolve payloads de household malformados', () => {
    expect(normalizeHouseholds('<html>erro de proxy</html>')).toEqual([]);
    expect(normalizeHouseholds({ items: hooks.list })).toEqual([]);
    expect(normalizeHousehold({ detail: 'not found' })).toBeNull();
  });

  test('não afirma um contexto pessoal quando o contexto ainda está indisponível', () => {
    expect(financialContextCopy(null)).toEqual({
      label: 'Contexto indisponível',
      description: 'Não foi possível determinar quais dados financeiros estão ativos.',
    });
  });

  test('expõe nomenclatura humana e troca pelo household canônico', async () => {
    render(<FinancialContextProvider><Probe /></FinancialContextProvider>);

    expect(screen.getByText('Finanças do casal')).toBeInTheDocument();
    expect(screen.getByText(/compartilhadas/i)).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Mudar para pessoal' }));

    expect(hooks.mutateAsync).toHaveBeenCalledWith({
      householdId: 10,
      sessionToken: 'session-a',
      payload: undefined,
    });
  });

  test('não troca silenciosamente enquanto existe formulário não salvo', async () => {
    render(<FinancialContextProvider><Probe dirty /></FinancialContextProvider>);

    await userEvent.click(screen.getByRole('button', { name: 'Mudar para pessoal' }));
    expect(hooks.mutateAsync).not.toHaveBeenCalled();
    expect(screen.getByRole('dialog', { name: 'Mudar de contexto financeiro?' })).toBeInTheDocument();

    await userEvent.click(screen.getByRole('button', { name: 'Descartar e mudar' }));
    expect(hooks.mutateAsync).toHaveBeenCalledTimes(1);
  });

  test('preserva o rascunho quando a troca confirmada falha', async () => {
    const onDiscard = vi.fn();
    hooks.mutateAsync.mockRejectedValueOnce(new Error('indisponível'));
    render(<FinancialContextProvider><Probe dirty onDiscard={onDiscard} /></FinancialContextProvider>);

    await userEvent.click(screen.getByRole('button', { name: 'Mudar para pessoal' }));
    await userEvent.click(screen.getByRole('button', { name: 'Descartar e mudar' }));

    expect(await screen.findByRole('alert')).toHaveTextContent(/não foi possível mudar/i);
    expect(onDiscard).not.toHaveBeenCalled();
    expect(screen.getByRole('dialog', { name: 'Mudar de contexto financeiro?' })).toBeInTheDocument();
  });

  test('permite navegar pelas opções com teclado e devolve o foco ao fechar', async () => {
    const user = userEvent.setup();
    render(<FinancialContextProvider><FinancialContextSwitcher /></FinancialContextProvider>);
    const trigger = screen.getByRole('button', { name: /Contexto financeiro: Finanças do casal/ });

    await user.click(trigger);
    const shared = screen.getByRole('menuitemradio', { name: /Finanças do casal/ });
    const personal = screen.getByRole('menuitemradio', { name: /Minhas finanças/ });
    expect(shared).toHaveFocus();
    await user.keyboard('{ArrowUp}');
    expect(personal).toHaveFocus();
    await user.keyboard('{Escape}');
    expect(screen.queryByRole('menu')).not.toBeInTheDocument();
    expect(trigger).toHaveFocus();
  });
});
