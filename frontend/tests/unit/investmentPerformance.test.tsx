import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, test, vi } from 'vitest';
import { ApiRequestError } from '../../src/services/api';

const serviceMock = vi.hoisted(() => ({
  getInvestmentPerformanceSummary: vi.fn(),
  getInvestmentDecisionPerformance: vi.fn(),
}));

vi.mock('../../src/features/investment-workspace/services/investmentPerformance.service', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../../src/features/investment-workspace/services/investmentPerformance.service')>()),
  getInvestmentPerformanceSummary: serviceMock.getInvestmentPerformanceSummary,
  getInvestmentDecisionPerformance: serviceMock.getInvestmentDecisionPerformance,
}));

import { DecisionPerformanceResults } from '../../src/features/investment-workspace/components/DecisionPerformanceResults';
import { RecommendationPerformancePanel } from '../../src/features/investment-workspace/components/RecommendationPerformancePanel';
import {
  normalizeInvestmentDecisionPerformance,
  normalizeInvestmentPerformanceSummary,
} from '../../src/features/investment-workspace/services/investmentPerformance.service';

const decisionId = '36000000-0000-4000-8000-000000000001';

function group(key: string, overrides = {}) {
  return {
    key,
    total: 1,
    total_eligible: 1,
    evaluated: 1,
    pending: 0,
    average_return_pct: 4,
    median_return_pct: 4,
    positive_pct: 100,
    negative_pct: 0,
    directional_accuracy_pct: 100,
    directional_sample: 1,
    neutral: 0,
    ...overrides,
  };
}

function summary(overrides = {}) {
  return {
    as_of: '2026-08-26T12:00:00Z',
    selected_horizon: null,
    total_decisions: 1,
    eligible_decisions: 3,
    evaluated: 1,
    pending: 2,
    average_return_pct: 4,
    median_return_pct: 4,
    positive_pct: 100,
    negative_pct: 0,
    directional_accuracy_pct: 100,
    directional_sample: 1,
    by_horizon: [group('1d'), group('7d', { total: 0, evaluated: 0, pending: 1, average_return_pct: null, directional_accuracy_pct: null }), group('30d', { total: 0, evaluated: 0, pending: 1, average_return_pct: null, directional_accuracy_pct: null })],
    by_action: [group('BUY')],
    by_asset: [group('PETR4')],
    by_risk: [group('LOW')],
    by_confidence: [group('HIGH')],
    by_score_band: [group('HIGH')],
    by_profile: [group('MODERATE')],
    by_rule_version: [group('rule-v1')],
    by_recommendation_engine_version: [group('engine-v1')],
    by_score_version: [group('score-v1')],
    by_guardrail_version: [group('guardrail-v1')],
    by_version_cohort: [group('engine-v1 | rule-v1 | score-v1 | guardrail-v1')],
    mixed_versions: false,
    calibration: [group('HIGH', { mean_confidence: 90, calibration_gap_pct: -10, diagnostic: 'INSUFFICIENT_SAMPLE' })],
    calibration_summary: { interpretation: 'INSUFFICIENT_SAMPLE' },
    timeline: [group('2026-08:1d', { period: '2026-08', horizon: '1d' })],
    ...overrides,
  };
}

function detail(overrides = {}) {
  return {
    decision_id: decisionId,
    asset: 'PETR4',
    action: 'BUY',
    decision_created_at: '2026-08-20T12:00:00Z',
    risk_level: 'LOW',
    confidence: '90',
    trend: 'UPTREND',
    recommendation_score: '85',
    investor_profile: 'MODERATE',
    rule_version: 'rule-v1',
    recommendation_engine_version: 'engine-v1',
    score_version: 'score-v1',
    guardrail_version: 'guardrail-v1',
    reference_price: '100',
    reference_price_timestamp: '2026-08-20T12:00:00Z',
    price_source: 'decision_snapshot',
    evaluations: [{
      horizon: '1d',
      reference_price: '100',
      reference_price_timestamp: '2026-08-20T12:00:00Z',
      price_source: 'decision_snapshot',
      evaluation_price: '104',
      evaluation_timestamp: '2026-08-21T23:59:59Z',
      evaluation_price_source: 'brapi',
      absolute_change: '4',
      return_pct: '4',
      max_favorable_excursion_pct: '6',
      max_adverse_excursion_pct: '-2',
      result_status: 'EVALUATED',
      result_classification: 'CORRECT',
      result_context: { action: 'BUY' },
      evaluation_policy_version: 'decision-performance-v1',
      evaluated_at: '2026-08-22T00:00:00Z',
    }],
    pending_horizons: ['7d', '30d'],
    eligible_pending_horizons: [],
    immature_horizons: ['7d', '30d'],
    ...overrides,
  };
}

function renderWithQuery(ui: React.ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } });
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
}

beforeEach(() => {
  serviceMock.getInvestmentPerformanceSummary.mockReset();
  serviceMock.getInvestmentDecisionPerformance.mockReset();
});

describe('normalização causal da performance', () => {
  test('aceita resumo completo, coortes e timeline sem perder estado parcial', () => {
    const normalized = normalizeInvestmentPerformanceSummary(summary());
    expect(normalized.evaluated).toBe(1);
    expect(normalized.pending).toBe(2);
    expect(normalized.by_horizon.map((item) => item.key)).toEqual(['1d', '7d', '30d']);
    expect(normalized.timeline[0].period).toBe('2026-08');
    expect(normalized.calibration[0].diagnostic).toBe('INSUFFICIENT_SAMPLE');
  });

  test('aceita decisão parcialmente avaliada e preserva preço, retorno e classificação', () => {
    const normalized = normalizeInvestmentDecisionPerformance(detail());
    expect(normalized.decision_id).toBe(decisionId);
    expect(normalized.evaluations[0].return_pct).toBe(4);
    expect(normalized.evaluations[0].result_classification).toBe('CORRECT');
    expect(normalized.pending_horizons).toEqual(['7d', '30d']);
  });

  test('rejeita IDs, horizontes, classificações e contagens inválidos', () => {
    expect(() => normalizeInvestmentDecisionPerformance(detail({ decision_id: '../../outro' }))).toThrow('incompleta');
    expect(() => normalizeInvestmentDecisionPerformance(detail({ evaluations: [{ ...detail().evaluations[0], horizon: '365d' }] }))).toThrow('incompleta');
    expect(() => normalizeInvestmentPerformanceSummary(summary({ evaluated: -1 }))).toThrow('contagens');
  });
});

describe('painel geral de performance', () => {
  test('permanece discreto e não consulta enquanto fechado', () => {
    renderWithQuery(<RecommendationPerformancePanel userId={36} />);
    expect(screen.getByRole('button', { name: /Ver performance/ })).toBeInTheDocument();
    expect(serviceMock.getInvestmentPerformanceSummary).not.toHaveBeenCalled();
  });

  test('não fabrica dados quando a Fase 35 está vazia', async () => {
    serviceMock.getInvestmentPerformanceSummary.mockResolvedValue(normalizeInvestmentPerformanceSummary(summary({ total_decisions: 0, eligible_decisions: 0, evaluated: 0, pending: 0, by_horizon: [], by_action: [], by_asset: [], by_risk: [], by_confidence: [], by_score_band: [], by_profile: [], by_rule_version: [], by_recommendation_engine_version: [], by_score_version: [], by_guardrail_version: [], by_version_cohort: [], calibration: [], timeline: [] })));
    renderWithQuery(<RecommendationPerformancePanel userId={36} />);
    await userEvent.click(screen.getByRole('button', { name: /Ver performance/ }));
    expect(await screen.findByText('Ainda não há decisões históricas')).toBeInTheDocument();
    expect(screen.getByText(/sem qualquer dado demonstrativo fictício/)).toBeInTheDocument();
  });

  test('mostra métricas por horizonte e ação com linguagem observacional', async () => {
    serviceMock.getInvestmentPerformanceSummary.mockResolvedValue(normalizeInvestmentPerformanceSummary(summary()));
    renderWithQuery(<RecommendationPerformancePanel userId={36} />);
    await userEvent.click(screen.getByRole('button', { name: /Ver performance/ }));
    expect(await screen.findByText('Avaliações concluídas')).toBeInTheDocument();
    expect(screen.getByText('Retorno observado médio')).toBeInTheDocument();
    expect(screen.getByText('Por horizonte')).toBeInTheDocument();
    expect(screen.getByText('Por decisão apresentada')).toBeInTheDocument();
    expect(screen.getByText(/Não representa operação executada/)).toBeInTheDocument();
    expect(screen.queryByText(/lucro garantido/i)).not.toBeInTheDocument();
  });

  test('erro fica contido sem questionar a decisão histórica', async () => {
    serviceMock.getInvestmentPerformanceSummary.mockRejectedValue(new ApiRequestError(500, 'Falha'));
    renderWithQuery(<RecommendationPerformancePanel userId={36} />);
    await userEvent.click(screen.getByRole('button', { name: /Ver performance/ }));
    expect(await screen.findByText('Performance indisponível')).toBeInTheDocument();
    expect(screen.getByText(/snapshots continuam preservados/)).toBeInTheDocument();
  });
});

describe('resultado posterior de uma decisão', () => {
  test('só consulta sob demanda e exibe horizontes avaliados e pendentes', async () => {
    serviceMock.getInvestmentDecisionPerformance.mockResolvedValue(normalizeInvestmentDecisionPerformance(detail()));
    renderWithQuery(<DecisionPerformanceResults decisionId={decisionId} />);
    expect(serviceMock.getInvestmentDecisionPerformance).not.toHaveBeenCalled();
    await userEvent.click(screen.getByRole('button', { name: 'Ver resultados posteriores' }));
    expect(await screen.findByText('O que aconteceu depois')).toBeInTheDocument();
    expect(screen.getByText('+4,00%')).toBeInTheDocument();
    expect(screen.getByText('Coerente')).toBeInTheDocument();
    expect(screen.getByText('Pendentes: 7 dias, 30 dias.')).toBeInTheDocument();
    expect(screen.getByText(/Não é resultado de uma operação real/)).toBeInTheDocument();
  });

  test('distingue imaturidade de preço ausente', async () => {
    serviceMock.getInvestmentDecisionPerformance.mockResolvedValue(normalizeInvestmentDecisionPerformance(detail({ evaluations: [], pending_horizons: ['1d', '7d', '30d'], eligible_pending_horizons: ['1d'], immature_horizons: ['7d', '30d'] })));
    renderWithQuery(<DecisionPerformanceResults decisionId={decisionId} />);
    await userEvent.click(screen.getByRole('button', { name: 'Ver resultados posteriores' }));
    expect(await screen.findByText(/horizonte maduro aguardando um preço temporalmente compatível/)).toBeInTheDocument();
  });
});
