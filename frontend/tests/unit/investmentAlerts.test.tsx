import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, test, vi } from 'vitest';
import { ApiRequestError } from '../../src/services/api';

const serviceMock = vi.hoisted(() => ({
  getSubscriptions: vi.fn(),
  createSubscription: vi.fn(),
  updateSubscription: vi.fn(),
  deleteSubscription: vi.fn(),
  getAlerts: vi.fn(),
  getDetail: vi.fn(),
  markRead: vi.fn(),
}));

vi.mock('../../src/features/investment-workspace/services/investmentAlerts.service', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../../src/features/investment-workspace/services/investmentAlerts.service')>()),
  getInvestmentAlertSubscriptions: serviceMock.getSubscriptions,
  createInvestmentAlertSubscription: serviceMock.createSubscription,
  updateInvestmentAlertSubscription: serviceMock.updateSubscription,
  deleteInvestmentAlertSubscription: serviceMock.deleteSubscription,
  getInvestmentAlerts: serviceMock.getAlerts,
  getInvestmentAlertDetail: serviceMock.getDetail,
  markInvestmentAlertRead: serviceMock.markRead,
}));

import {
  InvestmentAlertsPanel,
  InvestmentMonitoringControl,
} from '../../src/features/investment-workspace/components';
import {
  normalizeInvestmentAlertDetail,
  normalizeInvestmentAlertsPage,
  normalizeInvestmentAlertSubscriptions,
} from '../../src/features/investment-workspace/services/investmentAlerts.service';
import type {
  InvestmentAlertDetail,
  InvestmentAlertSubscription,
} from '../../src/features/investment-workspace/types/investmentWorkspace.types';


const DECISION_ID = '37000000-0000-4000-8000-000000000001';
const ALERT_ID = '37000000-0000-4000-8000-000000000002';
const timestamp = '2026-08-27T01:00:00.000Z';

const subscription: InvestmentAlertSubscription = {
  id: 7,
  asset: 'GARE11',
  market: 'FII',
  budget: 300,
  investor_profile: 'CONSERVATIVE',
  source_decision_id: DECISION_ID,
  enabled: true,
  alert_on_action_change: true,
  alert_on_score_change: true,
  alert_on_confidence_change: true,
  alert_on_risk_change: true,
  alert_on_new_opportunity: true,
  minimum_score_delta: 5,
  minimum_confidence_delta: 10,
  cooldown_minutes: 180,
  rule_version: 'investment-alerts-v1',
  created_at: timestamp,
  updated_at: timestamp,
};

const emptySubscriptions = { items: [], total: 0, active: 0, limit: 20 };
const filledSubscriptions = { items: [subscription], total: 1, active: 1, limit: 20 };
const alertItem = {
  alert_id: ALERT_ID,
  subscription_id: 7,
  decision_id: DECISION_ID,
  asset: 'GARE11',
  alert_type: 'NEW_OPPORTUNITY' as const,
  severity: 'HIGH' as const,
  delivery_channel: 'IN_APP' as const,
  message: 'A recomendação mudou de Aguardar para Comprar.',
  created_at: timestamp,
  read_at: null,
};
const alertsPage = {
  items: [alertItem],
  page: 1,
  page_size: 8,
  total: 1,
  total_pages: 1,
  unread_count: 1,
};
const emptyAlerts = { items: [], page: 1, page_size: 8, total: 0, total_pages: 0, unread_count: 0 };
const detail: InvestmentAlertDetail = {
  ...alertItem,
  previous_state: { action: 'WAIT', score: '70', confidence: '80', risk_level: 'LOW', trend: 'SIDEWAYS' },
  current_state: { action: 'BUY', score: '82', confidence: '92', risk_level: 'LOW', trend: 'UPTREND' },
  rule_version: 'investment-alerts-v1',
};

function renderWithClient(element: React.ReactElement) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 }, mutations: { retry: false } } });
  return render(<QueryClientProvider client={client}>{element}</QueryClientProvider>);
}

beforeEach(() => {
  Object.values(serviceMock).forEach((mock) => mock.mockReset());
  serviceMock.getSubscriptions.mockResolvedValue(emptySubscriptions);
  serviceMock.getAlerts.mockResolvedValue(emptyAlerts);
});

describe('fronteira tipada dos alertas', () => {
  test('normaliza monitoramento, paginação e snapshot comparativo completos', () => {
    const normalizedSubscriptions = normalizeInvestmentAlertSubscriptions({
      ...filledSubscriptions,
      items: [{ ...subscription, budget: '300.00', minimum_score_delta: '5', minimum_confidence_delta: '10' }],
    });
    const normalizedPage = normalizeInvestmentAlertsPage({ ...alertsPage, page_size: 8 });
    const normalizedDetail = normalizeInvestmentAlertDetail(detail);
    expect(normalizedSubscriptions.items[0].budget).toBe(300);
    expect(normalizedPage.unread_count).toBe(1);
    expect(normalizedDetail.previous_state.action).toBe('WAIT');
    expect(normalizedDetail.current_state.action).toBe('BUY');
  });

  test.each([
    { ...filledSubscriptions, items: [{ ...subscription, asset: "GARE11' OR 1=1" }] },
    { ...filledSubscriptions, active: 2 },
  ])('rejeita resposta de monitoramento inválida %#', (payload) => {
    expect(() => normalizeInvestmentAlertSubscriptions(payload)).toThrow(ApiRequestError);
  });

  test.each([
    { ...alertsPage, items: [{ ...alertItem, delivery_channel: 'SMS' }] },
    { ...alertsPage, unread_count: 2, total: 1 },
  ])('rejeita inbox inválida %#', (payload) => {
    expect(() => normalizeInvestmentAlertsPage(payload)).toThrow(ApiRequestError);
  });

  test('não fabrica contexto ausente no detalhe', () => {
    expect(() => normalizeInvestmentAlertDetail(alertItem)).toThrow(ApiRequestError);
  });
});

describe('controle de monitoramento do ativo', () => {
  test('ativa o ativo usando exclusivamente asset e decision_id auditável', async () => {
    serviceMock.createSubscription.mockResolvedValue(subscription);
    serviceMock.getSubscriptions.mockResolvedValueOnce(emptySubscriptions).mockResolvedValue(filledSubscriptions);
    renderWithClient(<InvestmentMonitoringControl userId={37} asset="GARE11" decisionId={DECISION_ID} />);
    await userEvent.click(await screen.findByRole('button', { name: /Monitorar ativo/ }));
    await waitFor(() => expect(serviceMock.createSubscription).toHaveBeenCalledWith({ asset: 'GARE11', source_decision_id: DECISION_ID }));
    expect(await screen.findByText('GARE11 passou a ser monitorado.')).toBeInTheDocument();
  });

  test('mostra ativo já monitorado e permite pausar sem recriar subscription', async () => {
    serviceMock.getSubscriptions.mockResolvedValue(filledSubscriptions);
    serviceMock.updateSubscription.mockResolvedValue({ ...subscription, enabled: false });
    renderWithClient(<InvestmentMonitoringControl userId={37} asset="GARE11" decisionId={DECISION_ID} />);
    expect(await screen.findByText('Monitoramento ativo')).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: /Pausar/ }));
    await waitFor(() => expect(serviceMock.updateSubscription).toHaveBeenCalledWith(7, { enabled: false }));
    expect(serviceMock.createSubscription).not.toHaveBeenCalled();
  });

  test('edita thresholds e cooldown em modal compacto', async () => {
    serviceMock.getSubscriptions.mockResolvedValue(filledSubscriptions);
    serviceMock.updateSubscription.mockResolvedValue(subscription);
    renderWithClient(<InvestmentMonitoringControl userId={37} asset="GARE11" decisionId={DECISION_ID} />);
    await userEvent.click(await screen.findByRole('button', { name: /Configurar/ }));
    const dialog = screen.getByRole('dialog');
    const cooldown = within(dialog).getByLabelText('Cooldown em minutos');
    await userEvent.clear(cooldown);
    await userEvent.type(cooldown, '240');
    await userEvent.click(within(dialog).getByRole('checkbox', { name: 'Mudança relevante de confiança' }));
    await userEvent.click(within(dialog).getByRole('button', { name: 'Salvar preferências' }));
    await waitFor(() => expect(serviceMock.updateSubscription).toHaveBeenCalledWith(7, expect.objectContaining({ cooldown_minutes: 240, alert_on_confidence_change: false })));
  });

  test('desativa definitivamente o monitoramento sem apagar alertas históricos no frontend', async () => {
    serviceMock.getSubscriptions.mockResolvedValue(filledSubscriptions);
    serviceMock.deleteSubscription.mockResolvedValue(undefined);
    renderWithClient(<InvestmentMonitoringControl userId={37} asset="GARE11" decisionId={DECISION_ID} />);
    await userEvent.click(await screen.findByRole('button', { name: /Configurar/ }));
    await userEvent.click(screen.getByRole('button', { name: /Excluir monitoramento/ }));
    await waitFor(() => expect(serviceMock.deleteSubscription).toHaveBeenCalledWith(7));
    expect(await screen.findByText('GARE11 deixou de ser monitorado.')).toBeInTheDocument();
  });

  test('trata loading, erro e decisão sem identificação sem quebrar layout', async () => {
    serviceMock.getSubscriptions.mockReturnValue(new Promise(() => undefined));
    const first = renderWithClient(<InvestmentMonitoringControl userId={37} asset="GARE11" decisionId={DECISION_ID} />);
    expect(await screen.findByText('Verificando monitoramentos...')).toBeInTheDocument();
    first.unmount();

    serviceMock.getSubscriptions.mockRejectedValue(new ApiRequestError(503, 'API indisponível'));
    const second = renderWithClient(<InvestmentMonitoringControl userId={37} asset="GARE11" decisionId={DECISION_ID} />);
    expect(await screen.findByText('Monitoramento indisponível')).toBeInTheDocument();
    second.unmount();

    renderWithClient(<InvestmentMonitoringControl userId={37} asset="GARE11" />);
    expect(screen.getByRole('button', { name: /Monitorar ativo/ })).toBeDisabled();
    expect(screen.getByText(/identificação auditável da decisão/)).toBeInTheDocument();
  });
});

describe('central de alertas in-app', () => {
  test('trata central vazia e todas as notificações lidas', async () => {
    renderWithClient(<InvestmentAlertsPanel userId={37} />);
    await userEvent.click(screen.getByRole('button', { name: /Abrir alertas/ }));
    expect(await screen.findByText('Nenhum alerta por enquanto')).toBeInTheDocument();
    await userEvent.click(screen.getByRole('checkbox', { name: 'Mostrar somente não lidos' }));
    expect(await screen.findByText('Todos os alertas foram lidos')).toBeInTheDocument();
  });

  test('exibe contador, severidade, mensagem factual e estado não lido', async () => {
    serviceMock.getAlerts.mockResolvedValue(alertsPage);
    renderWithClient(<InvestmentAlertsPanel userId={37} />);
    expect(await screen.findByLabelText('1 alertas não lidos')).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: /Abrir alertas/ }));
    expect(await screen.findByText('Nova oportunidade')).toBeInTheDocument();
    expect(screen.getByText('A recomendação mudou de Aguardar para Comprar.')).toBeInTheDocument();
    expect(screen.getByLabelText('Não lido')).toBeInTheDocument();
  });

  test('abre detalhe comparativo com decisão relacionada', async () => {
    serviceMock.getAlerts.mockResolvedValue(alertsPage);
    serviceMock.getDetail.mockResolvedValue(detail);
    renderWithClient(<InvestmentAlertsPanel userId={37} />);
    await userEvent.click(await screen.findByRole('button', { name: /Abrir alertas/ }));
    await userEvent.click(await screen.findByRole('button', { name: /A recomendação mudou/ }));
    expect(await screen.findByRole('heading', { name: 'GARE11' })).toBeInTheDocument();
    const before = screen.getByLabelText('Antes');
    const now = screen.getByLabelText('Agora');
    expect(within(before).getByText('Aguardar')).toBeInTheDocument();
    expect(within(now).getByText('Comprar')).toBeInTheDocument();
    expect(screen.getByText(DECISION_ID)).toBeInTheDocument();
  });

  test('marca como lido e invalida contador/inbox', async () => {
    serviceMock.getAlerts.mockResolvedValue(alertsPage);
    serviceMock.getDetail.mockResolvedValue(detail);
    serviceMock.markRead.mockResolvedValue({ ...alertItem, read_at: timestamp });
    renderWithClient(<InvestmentAlertsPanel userId={37} />);
    await userEvent.click(await screen.findByRole('button', { name: /Abrir alertas/ }));
    await userEvent.click(await screen.findByRole('button', { name: /A recomendação mudou/ }));
    await userEvent.click(await screen.findByRole('button', { name: 'Marcar como lido' }));
    await waitFor(() => expect(serviceMock.markRead).toHaveBeenCalledWith(ALERT_ID));
    await waitFor(() => expect(serviceMock.getAlerts.mock.calls.length).toBeGreaterThan(2));
  });

  test.each([
    [new ApiRequestError(503, 'API indisponível'), 'Central de alertas indisponível'],
    [new ApiRequestError(401, 'Sessão expirada', 'AUTH_EXPIRED'), 'Sessão encerrada'],
  ])('trata erro e sessão expirada: %s', async (error, title) => {
    serviceMock.getAlerts.mockRejectedValue(error);
    renderWithClient(<InvestmentAlertsPanel userId={37} />);
    await userEvent.click(screen.getByRole('button', { name: /Abrir alertas/ }));
    expect(await screen.findByText(title)).toBeInTheDocument();
  });

  test('trata loading e paginação sem remover a central', async () => {
    serviceMock.getAlerts
      .mockResolvedValueOnce({ ...alertsPage, page_size: 1 })
      .mockResolvedValueOnce({ ...alertsPage, total: 9, total_pages: 2 })
      .mockResolvedValueOnce({ ...alertsPage, page: 2, total: 9, total_pages: 2 });
    renderWithClient(<InvestmentAlertsPanel userId={37} />);
    await userEvent.click(await screen.findByRole('button', { name: /Abrir alertas/ }));
    expect(await screen.findByText('Página 1 de 2')).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: /Próxima/ }));
    expect(await screen.findByText('Página 2 de 2')).toBeInTheDocument();
    expect(serviceMock.getAlerts).toHaveBeenLastCalledWith(expect.objectContaining({ page: 2, pageSize: 8 }), expect.any(AbortSignal));
  });
});
