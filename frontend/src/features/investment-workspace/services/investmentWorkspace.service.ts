import { api, API_BASE_URL, ApiRequestError, normalizeApiError } from '../../../services/api';
import type {
  AlternativeComparison,
  BudgetRecommendation,
  DecisionCard,
  ExplainedBudgetAdvisorResponse,
  InvestmentWorkspaceFilters,
  RelativePosition,
  ScoreBreakdown,
} from '../types/investmentWorkspace.types';

const ENDPOINT = `${API_BASE_URL}/api/intelligence/budget-advisor`;
const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function asString(value: unknown) {
  return typeof value === 'string' && value.trim() ? value.trim() : undefined;
}

function asNullableString(value: unknown) {
  return value === null ? null : asString(value);
}

function asUuid(value: unknown) {
  const normalized = asString(value);
  return normalized && UUID_PATTERN.test(normalized) ? normalized.toLowerCase() : undefined;
}

function asIsoDate(value: unknown) {
  const normalized = asString(value);
  if (!normalized) return undefined;
  const timestamp = Date.parse(normalized);
  return Number.isFinite(timestamp) ? new Date(timestamp).toISOString() : undefined;
}

export function createDecisionRequestTrace() {
  const randomUuid = globalThis.crypto?.randomUUID?.bind(globalThis.crypto);
  return {
    decisionId: randomUuid?.(),
    correlationId: randomUuid?.(),
  };
}

function asStringList(value: unknown) {
  return Array.isArray(value)
    ? value.filter((item): item is string => typeof item === 'string' && Boolean(item.trim())).map((item) => item.trim())
    : [];
}

function asNumberLike(value: unknown, { min = 0, max = Number.POSITIVE_INFINITY } = {}) {
  if (typeof value !== 'number' && typeof value !== 'string') return undefined;
  if (typeof value === 'string' && !value.trim()) return undefined;
  const number = Number(value);
  if (!Number.isFinite(number) || number < min || number > max) return undefined;
  return typeof value === 'string' ? value.trim() : value;
}

function asScore(value: unknown) {
  return asNumberLike(value, { min: 0, max: 100 });
}

function asInteger(value: unknown) {
  const number = Number(value);
  return Number.isInteger(number) && number >= 0 ? number : undefined;
}

function asDecisionCard(value: unknown): DecisionCard | undefined {
  if (!isRecord(value)) return undefined;
  return {
    ticker: asString(value.ticker),
    action: asString(value.action),
    quantity: asNumberLike(value.quantity),
    price: asNumberLike(value.price),
    invested_amount: asNumberLike(value.invested_amount),
    remaining_budget: asNumberLike(value.remaining_budget),
    budget_usage_pct: asScore(value.budget_usage_pct),
    recommendation_score: asScore(value.recommendation_score),
    confidence_score: asScore(value.confidence_score),
    appreciation_signal: asString(value.appreciation_signal),
  };
}

function asScoreBreakdown(value: unknown): ScoreBreakdown | undefined {
  if (!isRecord(value)) return undefined;
  return {
    recommendation_score: asScore(value.recommendation_score),
    fundamental_score: asScore(value.fundamental_score),
    profile_score: asScore(value.profile_score),
    quality_score: asScore(value.quality_score),
    liquidity_score: asScore(value.liquidity_score),
    risk_score: asScore(value.risk_score),
    dividend_score: asScore(value.dividend_score),
    momentum_score: asScore(value.momentum_score),
  };
}

function asRelativePosition(value: unknown): RelativePosition | undefined {
  if (!isRecord(value)) return undefined;
  return {
    rank: asInteger(value.rank),
    total_candidates: asInteger(value.total_candidates),
    percentile_label: asString(value.percentile_label),
    text: asString(value.text),
  };
}

function asComparisons(value: unknown): AlternativeComparison[] {
  if (!Array.isArray(value)) return [];
  return value
    .filter(isRecord)
    .map((item) => ({ ticker: asString(item.ticker), reason: asString(item.reason) }))
    .filter((item) => item.ticker || item.reason);
}

function asRecommendation(value: unknown): BudgetRecommendation | null {
  if (!isRecord(value)) return null;
  const ticker = asString(value.ticker);
  const market = asString(value.market);
  if (!ticker || !market) return null;

  return {
    ticker,
    market,
    date: asString(value.date),
    price: asNumberLike(value.price),
    quantity_possible: asNumberLike(value.quantity_possible),
    invested_amount: asNumberLike(value.invested_amount),
    score_total: asScore(value.score_total),
    score_quality: asScore(value.score_quality),
    score_liquidity: asScore(value.score_liquidity),
    score_risk: asScore(value.score_risk),
    score_dividend: asScore(value.score_dividend),
    profile: asString(value.profile),
    profile_score: asScore(value.profile_score),
    recommendation_score: asScore(value.recommendation_score),
    status: asString(value.status),
    risk_level: asString(value.risk_level),
    trend_label: asNullableString(value.trend_label),
    momentum_score: asScore(value.momentum_score),
    trend_confidence: asNullableString(value.trend_confidence),
    trend_method: asNullableString(value.trend_method),
    recommendation_components_json: isRecord(value.recommendation_components_json) ? value.recommendation_components_json : null,
    reasons_json: Array.isArray(value.reasons_json)
      ? asStringList(value.reasons_json)
      : isRecord(value.reasons_json) ? value.reasons_json : null,
    recommendation_title: asString(value.recommendation_title),
    decision_summary: asString(value.decision_summary),
    executive_summary: asString(value.executive_summary),
    decision_card: asDecisionCard(value.decision_card),
    score_breakdown: asScoreBreakdown(value.score_breakdown),
    relative_position: asRelativePosition(value.relative_position),
    strengths: asStringList(value.strengths),
    attention_points: asStringList(value.attention_points),
    comparison_with_alternatives: asComparisons(value.comparison_with_alternatives),
    why_recommended: asStringList(value.why_recommended),
    appreciation_signal: asString(value.appreciation_signal),
    appreciation_text: asString(value.appreciation_text),
    confidence_score: asScore(value.confidence_score),
    confidence_label: asString(value.confidence_label),
    budget_usage_pct: asScore(value.budget_usage_pct),
    remaining_budget: asNumberLike(value.remaining_budget),
    explanation_quality: asString(value.explanation_quality),
    disclaimer: asString(value.disclaimer),
  };
}

function partialWarnings(item: BudgetRecommendation | null) {
  if (!item) return [];
  const decision = item.decision_card ?? {};
  const missing = [
    ['status', item.status],
    ['preço', item.price ?? decision.price],
    ['quantidade', item.quantity_possible ?? decision.quantity],
    ['valor investido', item.invested_amount ?? decision.invested_amount],
    ['saldo restante', item.remaining_budget ?? decision.remaining_budget],
    ['uso do orçamento', item.budget_usage_pct ?? decision.budget_usage_pct],
    ['Recommendation Score', item.recommendation_score ?? decision.recommendation_score],
    ['Confidence Score', item.confidence_score ?? decision.confidence_score],
    ['Confidence Label', item.confidence_label],
    ['qualidade da explicação', item.explanation_quality],
    ['risco', item.risk_level],
    ['tendência', item.trend_label],
    ['potencial de valorização', item.appreciation_signal ?? decision.appreciation_signal],
  ].filter(([, fieldValue]) => fieldValue === undefined || fieldValue === null);

  const warnings: string[] = [];
  if (missing.length) warnings.push(`Resposta parcial: a API não informou ${missing.map(([label]) => label).join(', ')}.`);

  const scoreFields = [
    ['Recommendation Score', item.score_breakdown?.recommendation_score ?? item.recommendation_score],
    ['Fundamental Score', item.score_breakdown?.fundamental_score ?? item.score_total],
    ['Profile Score', item.score_breakdown?.profile_score ?? item.profile_score],
    ['Quality Score', item.score_breakdown?.quality_score ?? item.score_quality],
    ['Liquidity Score', item.score_breakdown?.liquidity_score ?? item.score_liquidity],
    ['Risk Score', item.score_breakdown?.risk_score ?? item.score_risk],
    ['Dividend Score', item.score_breakdown?.dividend_score ?? item.score_dividend],
    ['Momentum Score', item.score_breakdown?.momentum_score ?? item.momentum_score],
  ].filter(([, fieldValue]) => fieldValue === undefined || fieldValue === null);
  if (scoreFields.length) warnings.push(`Score breakdown parcial: faltam ${scoreFields.map(([label]) => label).join(', ')}.`);

  const confidence = Number(item.confidence_score ?? decision.confidence_score);
  const informedConfidence = item.confidence_label?.toUpperCase();
  if (Number.isFinite(confidence) && informedConfidence) {
    const expectedConfidence = confidence >= 80 ? 'HIGH' : confidence >= 60 ? 'MEDIUM' : 'LOW';
    if (informedConfidence !== expectedConfidence) {
      warnings.push('Dados de confiança divergentes: Confidence Score e Confidence Label não pertencem à mesma faixa.');
    }
  }

  if (!item.executive_summary && !item.decision_summary && !(item.why_recommended?.length || item.strengths?.length)) {
    warnings.push('Resposta parcial: a API não retornou explicações para esta recomendação.');
  }
  return warnings;
}

function invalidResponse(message: string) {
  return new ApiRequestError(502, message, 'INVALID_RESPONSE');
}

export function normalizeInvestmentWorkspaceResponse(value: unknown): ExplainedBudgetAdvisorResponse {
  if (!isRecord(value)) throw invalidResponse('A API retornou uma resposta de recomendação inválida.');

  let bestRecommendation: BudgetRecommendation | null = null;
  if (value.best_recommendation !== null && value.best_recommendation !== undefined) {
    bestRecommendation = asRecommendation(value.best_recommendation);
    if (!bestRecommendation) throw invalidResponse('A recomendação principal retornada pela API não possui estrutura válida.');
  }

  const alternatives = Array.isArray(value.alternatives)
    ? value.alternatives.map(asRecommendation).filter((item): item is BudgetRecommendation => item !== null)
    : [];
  const integrationWarnings = partialWarnings(bestRecommendation);
  const decisionId = asUuid(value.decision_id);
  const correlationId = asUuid(value.correlation_id);
  if (value.decision_id !== undefined && !decisionId) {
    integrationWarnings.push('A API retornou um identificador de decisão inválido; ele não será exibido nem usado no histórico.');
  }
  if (value.correlation_id !== undefined && !correlationId) {
    integrationWarnings.push('A API retornou um identificador de correlação inválido.');
  }
  if (asString(value.audit_status)?.toUpperCase() === 'FAILED') {
    integrationWarnings.push('A recomendação foi calculada, mas o registro de auditoria não pôde ser confirmado.');
  }
  if (value.budget === undefined || asNumberLike(value.budget) === undefined) {
    integrationWarnings.push('Resposta parcial: o orçamento de referência não foi informado em formato válido.');
  }
  if (value.alternatives !== undefined && !Array.isArray(value.alternatives)) {
    integrationWarnings.push('Resposta parcial: a lista de alternativas foi descartada por formato inválido.');
  } else if (Array.isArray(value.alternatives) && alternatives.length !== value.alternatives.length) {
    const discarded = value.alternatives.length - alternatives.length;
    integrationWarnings.push(`Resposta parcial: ${discarded} ${discarded === 1 ? 'alternativa foi descartada' : 'alternativas foram descartadas'} por formato inválido.`);
  }

  return {
    decision_id: decisionId,
    correlation_id: correlationId,
    generated_at: asIsoDate(value.generated_at),
    decision_action: asString(value.decision_action),
    audit_status: asString(value.audit_status),
    budget: asNumberLike(value.budget) ?? '',
    market: asString(value.market) ?? '',
    profile: asString(value.profile) ?? 'MODERATE',
    best_recommendation: bestRecommendation,
    alternatives,
    disclaimer: asString(value.disclaimer),
    integration_warnings: integrationWarnings,
  };
}

export async function getInvestmentWorkspaceRecommendation(filters: InvestmentWorkspaceFilters, signal?: AbortSignal) {
  const trace = createDecisionRequestTrace();
  try {
    const response = await api.get<unknown>(ENDPOINT, {
      signal,
      headers: {
        ...(trace.decisionId ? { 'X-Decision-ID': trace.decisionId } : {}),
        ...(trace.correlationId ? { 'X-Correlation-ID': trace.correlationId } : {}),
      },
      params: {
        budget: filters.budget,
        market: filters.market,
        profile: filters.profile,
        limit: 20,
        include_warnings: filters.includeWarnings,
        explain: true,
      },
    });
    const normalized = normalizeInvestmentWorkspaceResponse(response.data);
    normalized.decision_id ??= asUuid(response.headers['x-decision-id']);
    normalized.correlation_id ??= asUuid(response.headers['x-correlation-id']);
    return normalized;
  } catch (error) {
    const normalized = normalizeApiError(error);
    if (normalized.code !== 'REQUEST_CANCELED') {
      console.error('[Vinance][investment-workspace] Falha na integração com budget-advisor.', {
        code: normalized.code,
        status: normalized.status,
        message: normalized.message,
        correlationId: normalized.correlationId ?? trace.correlationId,
      });
    }
    throw normalized;
  }
}
