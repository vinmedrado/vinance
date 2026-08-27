import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, test, vi } from 'vitest';
import { ApiRequestError } from '../../src/services/api';
import {
  decisionDetailResponse,
  decisionHistoryResponse,
  emptyDecisionHistoryResponse,
} from '../fixtures/investmentFixtures';

const serviceMock = vi.hoisted(() => ({
  getInvestmentDecisionHistory: vi.fn(),
  getInvestmentDecisionDetail: vi.fn(),
}));

vi.mock('../../src/features/investment-workspace/services/investmentDecisionHistory.service', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../../src/features/investment-workspace/services/investmentDecisionHistory.service')>()),
  getInvestmentDecisionHistory: serviceMock.getInvestmentDecisionHistory,
  getInvestmentDecisionDetail: serviceMock.getInvestmentDecisionDetail,
}));

import { DecisionHistoryPanel } from '../../src/features/investment-workspace/components/DecisionHistoryPanel';
import {
  normalizeDecisionDetailResponse,
  normalizeDecisionHistoryResponse,
} from '../../src/features/investment-workspace/services/investmentDecisionHistory.service';

function renderHistory() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } });
  return render(<QueryClientProvider client={client}><DecisionHistoryPanel userId={35} refreshDecisionId={decisionDetailResponse.decision_id} /></QueryClientProvider>);
}

async function openHistory() {
  await userEvent.click(screen.getByRole('button', { name: 'Ver histórico' }));
}

beforeEach(() => {
  serviceMock.getInvestmentDecisionHistory.mockReset();
  serviceMock.getInvestmentDecisionDetail.mockReset();
});

describe('normalização do histórico auditável', () => {
  test('preserva IDs, paginação e informações coerentes', () => {
    const history = normalizeDecisionHistoryResponse(decisionHistoryResponse);
    expect(history.items[0].decision_id).toBe('35000000-0000-4000-8000-000000000001');
    expect(history.items[0].recommendation).toBe('BUY');
    expect(history.items[0].invested_amount).toBe('296.28');
    expect(history.total_pages).toBe(1);
  });

  test('rejeita paginação e detalhe inválidos', () => {
    expect(() => normalizeDecisionHistoryResponse({ items: [], page: 'x' })).toThrow('paginação');
    expect(() => normalizeDecisionDetailResponse({ ...decisionDetailResponse, decision_id: '../../segredo' })).toThrow('detalhe');
  });

  test('snapshot detalhado mantém versionamento', () => {
    const detail = normalizeDecisionDetailResponse(decisionDetailResponse);
    expect(detail.snapshot_schema_version).toBe('investment-decision-audit-v1');
    expect(detail.rule_version).toBe('investment-decision-presentation-v1');
    expect(detail.recommendation_engine_version).toBe('budget-advisor-v1');
  });
});

describe('painel de histórico', () => {
  test('não consulta enquanto o painel está fechado', () => {
    renderHistory();
    expect(serviceMock.getInvestmentDecisionHistory).not.toHaveBeenCalled();
  });

  test('exibe loading independente da recomendação atual', async () => {
    serviceMock.getInvestmentDecisionHistory.mockReturnValue(new Promise(() => undefined));
    renderHistory();
    await openHistory();
    expect(screen.getByText('Carregando decisões recentes...')).toBeInTheDocument();
  });

  test('exibe histórico vazio sem quebrar o card', async () => {
    serviceMock.getInvestmentDecisionHistory.mockResolvedValue(normalizeDecisionHistoryResponse(emptyDecisionHistoryResponse));
    renderHistory();
    await openHistory();
    expect(await screen.findByText('Histórico vazio')).toBeInTheDocument();
    expect(screen.getByText('Sua próxima análise registrada aparecerá aqui.')).toBeInTheDocument();
  });

  test('erro e sessão expirada ficam contidos no histórico', async () => {
    serviceMock.getInvestmentDecisionHistory.mockRejectedValue(new ApiRequestError(401, 'Sessão expirada', 'AUTH_EXPIRED'));
    renderHistory();
    await openHistory();
    expect(await screen.findByText('Não foi possível carregar o histórico')).toBeInTheDocument();
    expect(screen.getByText('A decisão atual continua disponível. Tente carregar o histórico novamente.')).toBeInTheDocument();
  });

  test('abre item preenchido e mostra detalhe auditável', async () => {
    serviceMock.getInvestmentDecisionHistory.mockResolvedValue(normalizeDecisionHistoryResponse(decisionHistoryResponse));
    serviceMock.getInvestmentDecisionDetail.mockResolvedValue(normalizeDecisionDetailResponse(decisionDetailResponse));
    renderHistory();
    await openHistory();

    const item = await screen.findByRole('button', { name: /GARE11/ });
    expect(item).toHaveTextContent('Comprar');
    expect(item).toHaveTextContent('R$ 296,28');
    await userEvent.click(item);

    expect(await screen.findByText('Snapshot imutável')).toBeInTheDocument();
    expect(screen.getByText('Engine budget-advisor-v1 · Regras investment-decision-presentation-v1')).toBeInTheDocument();
    expect(screen.getByText('GARE11 lidera o ranking relativo para os filtros informados.')).toBeInTheDocument();
    expect(serviceMock.getInvestmentDecisionDetail).toHaveBeenCalledWith(decisionDetailResponse.decision_id, expect.any(AbortSignal));
  });

  test('pagina sem perder isolamento da query do usuário', async () => {
    serviceMock.getInvestmentDecisionHistory
      .mockResolvedValueOnce(normalizeDecisionHistoryResponse({ ...decisionHistoryResponse, total: 6, total_pages: 2 }))
      .mockResolvedValueOnce(normalizeDecisionHistoryResponse({ ...decisionHistoryResponse, page: 2, total: 6, total_pages: 2 }));
    renderHistory();
    await openHistory();
    await userEvent.click(await screen.findByRole('button', { name: /Próxima/ }));
    await waitFor(() => expect(serviceMock.getInvestmentDecisionHistory).toHaveBeenLastCalledWith(2, 5, expect.any(AbortSignal)));
  });
});
