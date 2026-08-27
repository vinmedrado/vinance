import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';
import type { ReactNode } from 'react';
import { beforeEach, describe, expect, test, vi } from 'vitest';
import { AppLayout } from '../../src/layouts/AppLayout';
import { RequireAuth } from '../../src/features/auth/components/RequireAuth';
import { ApiRequestError, clearSession, getAccessToken, setSession } from '../../src/services/api';
import { authenticatedUser, fakeAccessToken } from '../fixtures/investmentFixtures';

const authService = vi.hoisted(() => ({
  getMe: vi.fn(),
  login: vi.fn(),
  register: vi.fn(),
  logout: vi.fn(async () => undefined),
}));

vi.mock('../../src/features/auth/services/auth.service', () => authService);

function LoginProbe() {
  const location = useLocation();
  const reason = (location.state as { reason?: string } | null)?.reason ?? 'none';
  const from = (location.state as { from?: string } | null)?.from ?? 'none';
  return <div>Login {reason} {from}</div>;
}

function renderProtected(children: ReactNode = <div>Central autenticada</div>) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={['/investir?origem=teste#decisao']}>
        <Routes>
          <Route path="/login" element={<LoginProbe />} />
          <Route path="/investir" element={<RequireAuth>{children as React.ReactElement}</RequireAuth>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  authService.getMe.mockReset();
  authService.login.mockReset();
  authService.register.mockReset();
  authService.logout.mockReset();
});

describe('guard autenticado', () => {
  test('redireciona anônimo e preserva rota completa de retorno', async () => {
    renderProtected();
    expect(await screen.findByText('Login required /investir?origem=teste#decisao')).toBeInTheDocument();
    expect(authService.getMe).not.toHaveBeenCalled();
  });

  test('bloqueia a tela durante /me e libera usuário autenticado', async () => {
    let resolveUser!: (value: typeof authenticatedUser) => void;
    authService.getMe.mockReturnValue(new Promise((resolve) => { resolveUser = resolve; }));
    setSession(fakeAccessToken(), authenticatedUser);
    renderProtected();

    expect(screen.getByText('Validando sua sessão com o Vinance...')).toBeInTheDocument();
    expect(screen.queryByText('Central autenticada')).not.toBeInTheDocument();
    await act(async () => resolveUser(authenticatedUser));
    expect(await screen.findByText('Central autenticada')).toBeInTheDocument();
    expect(authService.getMe).toHaveBeenCalledTimes(1);
  });

  test('limpa token inválido e retorna ao login', async () => {
    authService.getMe.mockRejectedValue(new ApiRequestError(401, 'Invalid token', 'AUTH_EXPIRED'));
    setSession(fakeAccessToken(), authenticatedUser);
    renderProtected();

    expect(await screen.findByText('Login invalid /investir?origem=teste#decisao')).toBeInTheDocument();
    await waitFor(() => expect(getAccessToken()).toBeNull());
  });

  test('detecta JWT expirado sem consultar /me', async () => {
    setSession(fakeAccessToken(Date.now() - 60_000), authenticatedUser);
    renderProtected();

    expect(await screen.findByText('Login expired /investir?origem=teste#decisao')).toBeInTheDocument();
    expect(authService.getMe).not.toHaveBeenCalled();
    await waitFor(() => expect(getAccessToken()).toBeNull());
  });

  test('mantém sessão em erro de rede e permite revalidar', async () => {
    authService.getMe
      .mockRejectedValueOnce(new ApiRequestError(0, 'API offline ou indisponível no momento.', 'NETWORK_ERROR'))
      .mockResolvedValueOnce(authenticatedUser);
    setSession(fakeAccessToken(), authenticatedUser);
    renderProtected();

    expect(await screen.findByText('Não foi possível validar sua sessão')).toBeInTheDocument();
    expect(getAccessToken()).not.toBeNull();
    await userEvent.click(screen.getByRole('button', { name: 'Tentar novamente' }));
    expect(await screen.findByText('Central autenticada')).toBeInTheDocument();
  });

  test('logout limpa sessão e remove conteúdo protegido', async () => {
    authService.getMe.mockResolvedValue(authenticatedUser);
    authService.logout.mockImplementation(async () => {
      clearSession('logout');
    });
    setSession(fakeAccessToken(), authenticatedUser);
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={client}>
        <MemoryRouter initialEntries={['/investir']}>
          <Routes>
            <Route path="/login" element={<LoginProbe />} />
            <Route path="/" element={<RequireAuth><AppLayout /></RequireAuth>}>
              <Route path="investir" element={<div>Conteúdo protegido</div>} />
            </Route>
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>,
    );

    expect(await screen.findByText('Conteúdo protegido')).toBeInTheDocument();
    expect(authService.getMe).toHaveBeenCalledTimes(1);
    await userEvent.click(screen.getByRole('button', { name: /Sair/ }));
    expect(await screen.findByText(/Login/)).toBeInTheDocument();
    expect(screen.queryByText('Conteúdo protegido')).not.toBeInTheDocument();
    expect(getAccessToken()).toBeNull();
  });

  test('troca de token revalida /me sem reutilizar o usuário anterior', async () => {
    const secondUser = { ...authenticatedUser, id: 35, email: 'segunda-sessao@fixture.local', full_name: 'Segunda sessão' };
    authService.getMe.mockResolvedValueOnce(authenticatedUser).mockResolvedValueOnce(secondUser);
    setSession(fakeAccessToken(Date.now() + 60 * 60_000), authenticatedUser);
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={client}>
        <MemoryRouter initialEntries={['/investir']}>
          <Routes>
            <Route path="/" element={<RequireAuth><AppLayout /></RequireAuth>}>
              <Route path="investir" element={<div>Conteúdo protegido</div>} />
            </Route>
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>,
    );

    expect(await screen.findByText('Usuário Fase 34')).toBeInTheDocument();
    expect(authService.getMe).toHaveBeenCalledTimes(1);

    act(() => setSession(fakeAccessToken(Date.now() + 2 * 60 * 60_000), secondUser));

    expect(await screen.findByText('Segunda sessão')).toBeInTheDocument();
    expect(authService.getMe).toHaveBeenCalledTimes(2);
    expect(screen.queryByText('Usuário Fase 34')).not.toBeInTheDocument();
  });
});
