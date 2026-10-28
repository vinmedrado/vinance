import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest';
import { AppLayout } from '../../src/layouts/AppLayout';

const auth = vi.hoisted(() => ({
  logout: vi.fn(async () => undefined),
}));

vi.mock('../../src/features/auth/hooks/useAuth', () => ({
  useLogout: () => auth.logout,
  useCurrentUser: () => ({ data: { id: 9, email: 'pessoa@fixture.local', full_name: 'Pessoa Fixture' } }),
}));

vi.mock('../../src/hooks/useThemeMode', () => ({
  useThemeMode: () => ({ mode: 'dark', setMode: vi.fn() }),
}));

function renderLayout() {
  return render(
    <MemoryRouter initialEntries={['/dashboard']}>
      <Routes>
        <Route path="/" element={<AppLayout />}>
          <Route path="dashboard" element={<div>Resumo financeiro</div>} />
          <Route path="financial/manage" element={<div>Dados financeiros</div>} />
        </Route>
        <Route path="/login" element={<div>Entrar</div>} />
      </Routes>
    </MemoryRouter>,
  );
}

beforeEach(() => {
  auth.logout.mockClear();
  document.body.style.overflow = '';
});

afterEach(() => {
  document.body.style.overflow = '';
});

describe('navegação do produto', () => {
  test('separa destinos principais das áreas de gestão', () => {
    renderLayout();

    expect(screen.getByRole('navigation', { name: 'Navegação principal' })).toBeInTheDocument();
    expect(screen.getByRole('navigation', { name: 'Navegação principal no celular' })).toBeInTheDocument();
    expect(screen.getAllByRole('link', { name: /Início/ })).toHaveLength(2);
    expect(screen.getAllByRole('link', { name: /Assistente/ })).toHaveLength(2);
    expect(screen.getByRole('link', { name: /Dados financeiros/ })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /Trading simulado/ })).toBeInTheDocument();
    expect(screen.queryByRole('navigation', { name: 'Navegação principal no celular' })?.textContent).not.toContain('Trading');
    expect(screen.queryByText('Advisor IA')).not.toBeInTheDocument();
  });

  test('abre o menu secundário com conta, tema e saída', async () => {
    renderLayout();

    await userEvent.click(screen.getByRole('button', { name: 'Menu' }));

    expect(screen.getByRole('dialog', { name: 'Conta' })).toBeInTheDocument();
    expect(screen.getByRole('navigation', { name: 'Gestão e configurações' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Usar tema claro/ })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Sair da conta/ })).toBeInTheDocument();
  });

  test('mantém o foco no drawer, bloqueia o scroll e devolve o foco ao fechar', async () => {
    const user = userEvent.setup();
    renderLayout();
    const trigger = screen.getByRole('button', { name: 'Menu' });

    await user.click(trigger);
    const dialog = screen.getByRole('dialog', { name: 'Conta' });
    const closeButton = screen.getByRole('button', { name: 'Fechar menu' });
    expect(dialog).toBeInTheDocument();
    expect(closeButton).toHaveFocus();
    expect(document.body.style.overflow).toBe('hidden');

    await user.keyboard('{Escape}');
    expect(screen.queryByRole('dialog', { name: 'Conta' })).not.toBeInTheDocument();
    expect(document.body.style.overflow).toBe('');
    expect(trigger).toHaveFocus();
  });

  test('faz o foco circular entre o primeiro e o último controle do menu', async () => {
    const user = userEvent.setup();
    renderLayout();

    await user.click(screen.getByRole('button', { name: 'Menu' }));
    const closeButton = screen.getByRole('button', { name: 'Fechar menu' });
    const logoutButton = screen.getByRole('button', { name: /Sair da conta/ });

    closeButton.focus();
    await user.keyboard('{Shift>}{Tab}{/Shift}');
    expect(logoutButton).toHaveFocus();

    await user.tab();
    expect(closeButton).toHaveFocus();
  });
});
