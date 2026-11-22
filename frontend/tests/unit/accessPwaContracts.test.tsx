import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, test, vi } from 'vitest';
import { LoginPage } from '../../src/pages/LoginPage';
import { takeTokenFromFragment } from '../../src/features/platform-access/services/access.service';

const root = resolve(import.meta.dirname, '../..');
const auth = vi.hoisted(() => ({ mutateAsync: vi.fn(), reset: vi.fn(), isPending: false, error: null }));
const access = vi.hoisted(() => ({
  getAccessCapabilities: vi.fn(async () => ({
    access_mode: 'INVITE_ONLY', public_signup: false, bootstrap_available: true,
    invite_only: true, email_delivery_available: false,
    password_recovery_delivery_available: false, cloudflare_access_automation_available: false,
  })),
}));

vi.mock('../../src/features/auth/hooks/useAuth', () => ({ useLogin: () => auth }));
vi.mock('../../src/features/platform-access/services/access.service', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../../src/features/platform-access/services/access.service')>()),
  getAccessCapabilities: access.getAccessCapabilities,
}));

beforeEach(() => { access.getAccessCapabilities.mockClear(); auth.mutateAsync.mockClear(); });

describe('acesso invite-only e PWA seguro', () => {
  test('login não oferece cadastro público e aponta para convite, recuperação e bootstrap autorizado', async () => {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(<QueryClientProvider client={client}><MemoryRouter><LoginPage /></MemoryRouter></QueryClientProvider>);
    expect(screen.queryByText('Criar nova conta')).not.toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Tenho um convite' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Recuperar acesso' })).toBeInTheDocument();
    expect(await screen.findByRole('link', { name: 'Configurar primeira conta' })).toBeInTheDocument();
  });

  test('token vindo do fragmento é removido da URL e não vai para storage', () => {
    window.history.replaceState({}, '', '/access/invitation#token=segredo-de-uso-unico');
    expect(takeTokenFromFragment()).toBe('segredo-de-uso-unico');
    expect(window.location.hash).toBe('');
    expect(localStorage.length).toBe(0);
  });

  test('manifesto possui identidade instalável completa', () => {
    const manifest = JSON.parse(readFileSync(resolve(root, 'public/manifest.webmanifest'), 'utf8'));
    expect(manifest).toMatchObject({ id: '/', name: 'VinanceOS', short_name: 'Vinance', start_url: '/dashboard', scope: '/', display: 'standalone' });
    expect(manifest.icons).toEqual(expect.arrayContaining([
      expect.objectContaining({ sizes: '192x192' }),
      expect.objectContaining({ sizes: '512x512' }),
      expect.objectContaining({ purpose: 'maskable' }),
    ]));
  });

  test('service worker nunca persiste respostas da API financeira', () => {
    const source = readFileSync(resolve(root, 'public/sw.js'), 'utf8');
    const offline = readFileSync(resolve(root, 'public/offline.html'), 'utf8');
    expect(source).toContain("url.pathname.startsWith('/api/')");
    expect(source).toContain('event.respondWith(fetch(request))');
    expect(source).not.toMatch(/cache\.put\(request[\s\S]{0,120}\/api\//);
    expect(offline).toContain('Sem conexão');
  });

  test('chave privada VAPID não aparece no código ou no manifesto', () => {
    const publicFiles = ['public/sw.js', 'public/manifest.webmanifest', 'src/features/notifications/services/notifications.service.ts'];
    for (const file of publicFiles) {
      expect(readFileSync(resolve(root, file), 'utf8')).not.toContain('VAPID_PRIVATE_KEY');
    }
  });

  test('desativar um dispositivo não desliga silenciosamente os demais', () => {
    const service = readFileSync(
      resolve(root, 'src/features/notifications/services/notifications.service.ts'),
      'utf8',
    );
    const settings = readFileSync(resolve(root, 'src/pages/AccountSettingsPage.tsx'), 'utf8');
    expect(service).not.toContain('saveNotificationPreferences({ push_enabled: false })');
    expect(service).toContain('isPushEnabledForCurrentInstallation');
    expect(settings).toContain('isPushEnabledForCurrentInstallation');
  });
});
