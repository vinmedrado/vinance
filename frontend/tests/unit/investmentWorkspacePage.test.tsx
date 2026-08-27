import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, test, vi } from 'vitest';
import { InvestmentWorkspacePage } from '../../src/pages/InvestmentWorkspacePage';
import { ApiRequestError } from '../../src/services/api';
import {
  completeBudgetResponse,
  bottomRankedResponse,
  contradictoryAvoidResponse,
  divergentConfidenceResponse,
  emptyBudgetResponse,
  lowScoreResponse,
  partialBudgetResponse,
} from '../fixtures/investmentFixtures';

const serviceMock = vi.hoisted(() => ({ getInvestmentWorkspaceRecommendation: vi.fn() }));

vi.mock('../../src/features/investment-workspace/services/investmentWorkspace.service', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../../src/features/investment-workspace/services/investmentWorkspace.service')>()),
  getInvestmentWorkspaceRecommendation: serviceMock.getInvestmentWorkspaceRecommendation,
}));

import { normalizeInvestmentWorkspaceResponse } from '../../src/features/investment-workspace/services/investmentWorkspace.service';

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } });
  return render(<QueryClientProvider client={client}><InvestmentWorkspacePage /></QueryClientProvider>);
}

async function analyze() {
  await userEvent.click(screen.getByRole('button', { name: 'Analisar orçamento' }));
}

beforeEach(() => {
  serviceMock.getInvestmentWorkspaceRecommendation.mockReset();
});

describe('estados da central de decisão', () => {
  test('exibe estado inicial antes da consulta', () => {
    renderPage();
    expect(screen.getByText('Pronto para analisar')).toBeInTheDocument();
    expect(serviceMock.getInvestmentWorkspaceRecommendation).not.toHaveBeenCalled();
  });

  test('exibe loading da recomendação sem quebrar o formulário', async () => {
    serviceMock.getInvestmentWorkspaceRecommendation.mockReturnValue(new Promise(() => undefined));
    renderPage();
    await analyze();
    expect(screen.getByText('Comparando oportunidades para seu perfil...')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Analisando/ })).toBeDisabled();
  });

  test.each([
    [new ApiRequestError(500, 'Falha interna'), 'Não foi possível gerar a recomendação'],
    [new ApiRequestError(0, 'API offline', 'NETWORK_ERROR'), 'Serviço temporariamente indisponível'],
    [new ApiRequestError(0, 'A solicitação excedeu o tempo limite.', 'TIMEOUT'), 'A análise demorou mais que o esperado'],
    [new ApiRequestError(502, 'Payload inválido', 'INVALID_RESPONSE'), 'Resposta inesperada da API'],
  ])('apresenta erro seguro para %s', async (error, title) => {
    serviceMock.getInvestmentWorkspaceRecommendation.mockRejectedValue(error);
    renderPage();
    await analyze();
    expect(await screen.findByText(title)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Tentar novamente' })).toBeInTheDocument();
  });

  test('trata resposta vazia como ausência de recomendação', async () => {
    serviceMock.getInvestmentWorkspaceRecommendation.mockResolvedValue(normalizeInvestmentWorkspaceResponse(emptyBudgetResponse));
    renderPage();
    await analyze();
    expect(await screen.findByText('Nenhuma recomendação disponível')).toBeInTheDocument();
  });

  test('renderiza resposta parcial com aviso, fallbacks e ausência de alternativas', async () => {
    serviceMock.getInvestmentWorkspaceRecommendation.mockResolvedValue(normalizeInvestmentWorkspaceResponse(partialBudgetResponse));
    const { container } = renderPage();
    await analyze();

    expect(await screen.findByText('PARC11')).toBeInTheDocument();
    expect(screen.getByText('Dados parciais recebidos')).toBeInTheDocument();
    expect(screen.getByText('Rating indisponível')).toBeInTheDocument();
    expect(container.querySelector('.vn-score-gauge--neutral')).toBeInTheDocument();
    expect(container.querySelector('.vn-score-gauge--success')).not.toBeInTheDocument();
    expect(screen.getByText('A API retornou apenas a recomendação principal.')).toBeInTheDocument();
    expect(screen.getAllByText(/Nenhum item foi informado pela API/).length).toBeGreaterThan(0);
  });

  test('renderiza resposta completa e todos os blocos decisórios', async () => {
    serviceMock.getInvestmentWorkspaceRecommendation.mockResolvedValue(normalizeInvestmentWorkspaceResponse(completeBudgetResponse));
    renderPage();
    await analyze();

    expect(await screen.findByText('GARE11')).toBeInTheDocument();
    expect(screen.getAllByText('Comprar').length).toBeGreaterThan(0);
    expect(screen.getByText('Chance quantitativa')).toBeInTheDocument();
    expect(screen.getByText('Composição dos scores')).toBeInTheDocument();
    expect(screen.getByText('Outros ativos avaliados')).toBeInTheDocument();
    expect(screen.getByText('Decisão registrada')).toBeInTheDocument();
    expect(screen.getByText('35000000')).toBeInTheDocument();
    await userEvent.click(screen.getByText('Decisão registrada'));
    expect(screen.getByText(completeBudgetResponse.decision_id)).toBeInTheDocument();
    expect(screen.getByText(completeBudgetResponse.correlation_id)).toBeInTheDocument();
  });

  test('reconsulta mantendo o resultado anterior claramente identificado', async () => {
    let resolveRefresh!: (value: ReturnType<typeof normalizeInvestmentWorkspaceResponse>) => void;
    serviceMock.getInvestmentWorkspaceRecommendation
      .mockResolvedValueOnce(normalizeInvestmentWorkspaceResponse(completeBudgetResponse))
      .mockReturnValueOnce(new Promise((resolve) => { resolveRefresh = resolve; }));
    renderPage();
    await analyze();
    expect(await screen.findByText('GARE11')).toBeInTheDocument();

    await analyze();
    expect(screen.getByText('Atualizando análise — o resultado abaixo ainda é o anterior.')).toBeInTheDocument();
    expect(screen.getByText('GARE11')).toBeInTheDocument();
    await act(async () => resolveRefresh(normalizeInvestmentWorkspaceResponse(completeBudgetResponse)));
    await waitFor(() => expect(screen.queryByText('Atualizando análise — o resultado abaixo ainda é o anterior.')).not.toBeInTheDocument());
    expect(serviceMock.getInvestmentWorkspaceRecommendation).toHaveBeenCalledTimes(2);
  });
});

describe('coerência visual', () => {
  test('risco alto domina copy, rating e tom mesmo com scores otimistas', async () => {
    serviceMock.getInvestmentWorkspaceRecommendation.mockResolvedValue(normalizeInvestmentWorkspaceResponse(contradictoryAvoidResponse));
    const { container } = renderPage();
    await analyze();

    expect(await screen.findByText('Compra não indicada neste cenário')).toBeInTheDocument();
    expect(screen.getAllByText('Evitar').length).toBeGreaterThan(0);
    expect(screen.getByText('1 de 5 estrelas: Evitar')).toBeInTheDocument();
    expect(container.querySelector('.vn-decision-hero--danger')).toBeInTheDocument();
    expect(container.querySelector('.vn-opportunity-rating--danger')).toBeInTheDocument();
    expect(screen.queryByText('Os sinais atuais sustentam uma decisão de compra.')).not.toBeInTheDocument();
    expect(screen.queryByText('Excelente oportunidade com grande potencial.')).not.toBeInTheDocument();
    expect(screen.getByText('O ativo apresenta sinais técnicos muito positivos.')).not.toBeVisible();
    expect(screen.getByText('Contexto técnico original da API — não altera a decisão visual')).toBeVisible();
    expect(screen.getByText('Entenda por que a compra não é indicada')).toBeInTheDocument();
    expect(screen.getByText(/Score quantitativo alto, mas a decisão permanece Evitar/)).toBeInTheDocument();
    expect(container.querySelector('.vn-trend-reading--success')).toBeInTheDocument();
    expect(container.querySelector('.vn-potential-badge--success')).toBeInTheDocument();
    expect(container.querySelector('.vn-checklist-card--decision-danger')).not.toBeInTheDocument();

    const blockedAlternative = screen.getByLabelText('Alternativa 3: RZTR11');
    expect(blockedAlternative.querySelector('.vn-alternative-action--danger')).toBeInTheDocument();
    expect(blockedAlternative.querySelector('.vn-alternative-item__trend--success')).toBeInTheDocument();
  });

  test('score ruim nunca recebe medidor positivo', async () => {
    serviceMock.getInvestmentWorkspaceRecommendation.mockResolvedValue(normalizeInvestmentWorkspaceResponse(lowScoreResponse));
    const { container } = renderPage();
    await analyze();

    expect(await screen.findByText('BAIX11')).toBeInTheDocument();
    expect(screen.getByText('Baixa')).toBeInTheDocument();
    expect(container.querySelector('.vn-score-gauge--danger')).toBeInTheDocument();
    expect(container.querySelector('.vn-score-gauge--success')).not.toBeInTheDocument();
  });

  test('confiança textual divergente é sinalizada e o score numérico vira fonte visual', async () => {
    serviceMock.getInvestmentWorkspaceRecommendation.mockResolvedValue(normalizeInvestmentWorkspaceResponse(divergentConfidenceResponse));
    renderPage();
    await analyze();

    expect(await screen.findByText('CONF11')).toBeInTheDocument();
    expect(screen.getAllByText(/Dados de confiança divergentes/).length).toBeGreaterThanOrEqual(2);
    const confidenceMetric = screen.getByText('Nível de confiança').closest('div');
    expect(confidenceMetric).not.toBeNull();
    expect(within(confidenceMetric as HTMLElement).getByText('Baixa')).toBeInTheDocument();
    expect(within(confidenceMetric as HTMLElement).queryByText('Alta')).not.toBeInTheDocument();
    expect(screen.getByText(/Score quantitativo alto, mas a decisão permanece Aguardar/)).toBeInTheDocument();
  });

  test('posição inferior no ranking nunca recebe badge positivo', async () => {
    serviceMock.getInvestmentWorkspaceRecommendation.mockResolvedValue(normalizeInvestmentWorkspaceResponse(bottomRankedResponse));
    const { container } = renderPage();
    await analyze();

    expect(await screen.findByText('BOTTOM11')).toBeInTheDocument();
    expect(screen.getByText('Faixa inferior de 50%')).toBeInTheDocument();
    expect(container.querySelector('.vn-relative-ranking__label--danger')).toBeInTheDocument();
    expect(container.querySelector('.vn-relative-ranking__label--success')).not.toBeInTheDocument();
  });
});
