import { api, ApiRequestError, normalizeApiError } from '../../../services/api';
import type {
  InvestmentDecisionPerformanceDetail,
  InvestmentPerformanceEvaluation,
  InvestmentPerformanceSummary,
  PerformanceClassification,
  PerformanceHorizon,
  PerformanceMetricGroup,
} from '../types/investmentWorkspace.types';

const SUMMARY_ENDPOINT = '/investments/performance';
const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
const HORIZONS = new Set<PerformanceHorizon>(['1d', '7d', '30d']);
const CLASSIFICATIONS = new Set<PerformanceClassification>([
  'STRONGLY_CORRECT', 'CORRECT', 'NEUTRAL', 'INCORRECT', 'STRONGLY_INCORRECT',
]);

function invalidResponse(message: string) {
  return new ApiRequestError(502, message, 'INVALID_RESPONSE');
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function text(value: unknown) {
  return typeof value === 'string' && value.trim() ? value.trim() : undefined;
}

function uuid(value: unknown) {
  const normalized = text(value);
  return normalized && UUID_PATTERN.test(normalized) ? normalized.toLowerCase() : undefined;
}

function isoDate(value: unknown) {
  const normalized = text(value);
  return normalized && Number.isFinite(Date.parse(normalized)) ? new Date(normalized).toISOString() : undefined;
}

function number(value: unknown) {
  if (value === null || value === undefined || value === '') return undefined;
  const normalized = Number(value);
  return Number.isFinite(normalized) ? normalized : undefined;
}

function nonNegativeInteger(value: unknown) {
  const normalized = number(value);
  return normalized !== undefined && normalized >= 0 ? Math.trunc(normalized) : undefined;
}

function nullableNumber(value: unknown) {
  if (value === null) return null;
  return number(value);
}

function horizon(value: unknown): PerformanceHorizon | undefined {
  const normalized = text(value) as PerformanceHorizon | undefined;
  return normalized && HORIZONS.has(normalized) ? normalized : undefined;
}

function horizonList(value: unknown): PerformanceHorizon[] | undefined {
  if (!Array.isArray(value)) return undefined;
  const normalized = value.map(horizon);
  return normalized.every(Boolean) ? normalized as PerformanceHorizon[] : undefined;
}

function group(value: unknown): PerformanceMetricGroup | null {
  if (!isRecord(value)) return null;
  const key = text(value.key);
  const total = nonNegativeInteger(value.total);
  const totalEligible = nonNegativeInteger(value.total_eligible);
  const evaluated = nonNegativeInteger(value.evaluated);
  const pending = nonNegativeInteger(value.pending);
  const directionalSample = nonNegativeInteger(value.directional_sample);
  const neutral = nonNegativeInteger(value.neutral);
  if (!key || [total, totalEligible, evaluated, pending, directionalSample, neutral].some((item) => item === undefined)) return null;
  return {
    key,
    total: total!,
    total_eligible: totalEligible!,
    evaluated: evaluated!,
    pending: pending!,
    average_return_pct: nullableNumber(value.average_return_pct),
    median_return_pct: nullableNumber(value.median_return_pct),
    positive_pct: nullableNumber(value.positive_pct),
    negative_pct: nullableNumber(value.negative_pct),
    directional_accuracy_pct: nullableNumber(value.directional_accuracy_pct),
    directional_sample: directionalSample!,
    neutral: neutral!,
    period: text(value.period),
    horizon: horizon(value.horizon),
    mean_confidence: nullableNumber(value.mean_confidence),
    calibration_gap_pct: nullableNumber(value.calibration_gap_pct),
    diagnostic: text(value.diagnostic),
  };
}

function groups(value: unknown, label: string) {
  if (!Array.isArray(value)) throw invalidResponse(`A API retornou ${label} inválido.`);
  const normalized = value.map(group);
  if (normalized.some((item) => item === null)) throw invalidResponse(`A API retornou ${label} inválido.`);
  return normalized as PerformanceMetricGroup[];
}

export function normalizeInvestmentPerformanceSummary(value: unknown): InvestmentPerformanceSummary {
  if (!isRecord(value)) throw invalidResponse('A API retornou um resumo de performance inválido.');
  const asOf = isoDate(value.as_of);
  const selectedHorizon = value.selected_horizon === null ? null : horizon(value.selected_horizon);
  const totalDecisions = nonNegativeInteger(value.total_decisions);
  const eligibleDecisions = nonNegativeInteger(value.eligible_decisions);
  const evaluated = nonNegativeInteger(value.evaluated);
  const pending = nonNegativeInteger(value.pending);
  const directionalSample = nonNegativeInteger(value.directional_sample);
  if (!asOf || [totalDecisions, eligibleDecisions, evaluated, pending, directionalSample].some((item) => item === undefined)) {
    throw invalidResponse('A API retornou contagens de performance inválidas.');
  }
  const calibrationSummary = isRecord(value.calibration_summary) ? value.calibration_summary : undefined;
  if (!calibrationSummary || typeof value.mixed_versions !== 'boolean') throw invalidResponse('A API retornou analytics de performance incompletos.');
  return {
    as_of: asOf,
    selected_horizon: selectedHorizon,
    total_decisions: totalDecisions!,
    eligible_decisions: eligibleDecisions!,
    evaluated: evaluated!,
    pending: pending!,
    average_return_pct: nullableNumber(value.average_return_pct),
    median_return_pct: nullableNumber(value.median_return_pct),
    positive_pct: nullableNumber(value.positive_pct),
    negative_pct: nullableNumber(value.negative_pct),
    directional_accuracy_pct: nullableNumber(value.directional_accuracy_pct),
    directional_sample: directionalSample!,
    by_horizon: groups(value.by_horizon, 'horizontes'),
    by_action: groups(value.by_action, 'ações'),
    by_asset: groups(value.by_asset, 'ativos'),
    by_risk: groups(value.by_risk, 'riscos'),
    by_confidence: groups(value.by_confidence, 'confiança'),
    by_score_band: groups(value.by_score_band, 'faixas de score'),
    by_profile: groups(value.by_profile, 'perfis'),
    by_rule_version: groups(value.by_rule_version, 'versões de regra'),
    by_recommendation_engine_version: groups(value.by_recommendation_engine_version, 'versões do engine'),
    by_score_version: groups(value.by_score_version, 'versões de score'),
    by_guardrail_version: groups(value.by_guardrail_version, 'versões de guardrail'),
    by_version_cohort: groups(value.by_version_cohort, 'coortes de versão'),
    mixed_versions: value.mixed_versions,
    calibration: groups(value.calibration, 'calibração'),
    calibration_summary: calibrationSummary,
    timeline: groups(value.timeline, 'linha do tempo'),
  };
}

function evaluation(value: unknown): InvestmentPerformanceEvaluation | null {
  if (!isRecord(value)) return null;
  const normalizedHorizon = horizon(value.horizon);
  const classification = text(value.result_classification) as PerformanceClassification | undefined;
  const referenceTimestamp = isoDate(value.reference_price_timestamp);
  const evaluationTimestamp = isoDate(value.evaluation_timestamp);
  const evaluatedAt = isoDate(value.evaluated_at);
  const referencePrice = number(value.reference_price);
  const evaluationPrice = number(value.evaluation_price);
  const absoluteChange = number(value.absolute_change);
  const returnPct = number(value.return_pct);
  if (!normalizedHorizon || !classification || !CLASSIFICATIONS.has(classification) || !referenceTimestamp || !evaluationTimestamp || !evaluatedAt || [referencePrice, evaluationPrice, absoluteChange, returnPct].some((item) => item === undefined) || value.result_status !== 'EVALUATED' || !isRecord(value.result_context)) return null;
  const priceSource = text(value.price_source);
  const evaluationSource = text(value.evaluation_price_source);
  const policyVersion = text(value.evaluation_policy_version);
  if (!priceSource || !evaluationSource || !policyVersion) return null;
  return {
    horizon: normalizedHorizon,
    reference_price: referencePrice!,
    reference_price_timestamp: referenceTimestamp,
    price_source: priceSource,
    evaluation_price: evaluationPrice!,
    evaluation_timestamp: evaluationTimestamp,
    evaluation_price_source: evaluationSource,
    absolute_change: absoluteChange!,
    return_pct: returnPct!,
    max_favorable_excursion_pct: nullableNumber(value.max_favorable_excursion_pct),
    max_adverse_excursion_pct: nullableNumber(value.max_adverse_excursion_pct),
    result_status: 'EVALUATED',
    result_classification: classification,
    result_context: value.result_context,
    evaluation_policy_version: policyVersion,
    evaluated_at: evaluatedAt,
  };
}

export function normalizeInvestmentDecisionPerformance(value: unknown): InvestmentDecisionPerformanceDetail {
  if (!isRecord(value)) throw invalidResponse('A API retornou performance de decisão inválida.');
  const decisionId = uuid(value.decision_id);
  const asset = text(value.asset);
  const action = text(value.action) as 'BUY' | 'WAIT' | 'AVOID' | undefined;
  const createdAt = isoDate(value.decision_created_at);
  const ruleVersion = text(value.rule_version);
  const engineVersion = text(value.recommendation_engine_version);
  const evaluations = Array.isArray(value.evaluations) ? value.evaluations.map(evaluation) : [];
  const pending = horizonList(value.pending_horizons);
  const eligiblePending = horizonList(value.eligible_pending_horizons);
  const immature = horizonList(value.immature_horizons);
  if (!decisionId || !asset || !action || !['BUY', 'WAIT', 'AVOID'].includes(action) || !createdAt || !ruleVersion || !engineVersion || !Array.isArray(value.evaluations) || evaluations.some((item) => item === null) || !pending || !eligiblePending || !immature) {
    throw invalidResponse('A API retornou performance de decisão incompleta.');
  }
  return {
    decision_id: decisionId,
    asset,
    action,
    decision_created_at: createdAt,
    risk_level: value.risk_level === null ? null : text(value.risk_level),
    confidence: nullableNumber(value.confidence),
    trend: value.trend === null ? null : text(value.trend),
    recommendation_score: nullableNumber(value.recommendation_score),
    investor_profile: value.investor_profile === null ? null : text(value.investor_profile),
    rule_version: ruleVersion,
    recommendation_engine_version: engineVersion,
    score_version: value.score_version === null ? null : text(value.score_version),
    guardrail_version: value.guardrail_version === null ? null : text(value.guardrail_version),
    reference_price: nullableNumber(value.reference_price),
    reference_price_timestamp: value.reference_price_timestamp === null ? null : isoDate(value.reference_price_timestamp),
    price_source: value.price_source === null ? null : text(value.price_source),
    evaluations: evaluations as InvestmentPerformanceEvaluation[],
    pending_horizons: pending,
    eligible_pending_horizons: eligiblePending,
    immature_horizons: immature,
  };
}

export async function getInvestmentPerformanceSummary(signal?: AbortSignal) {
  try {
    const { data } = await api.get<unknown>(SUMMARY_ENDPOINT, { signal });
    return normalizeInvestmentPerformanceSummary(data);
  } catch (error) {
    throw normalizeApiError(error);
  }
}

export async function getInvestmentDecisionPerformance(decisionId: string, signal?: AbortSignal) {
  const normalizedId = uuid(decisionId);
  if (!normalizedId) throw new ApiRequestError(404, 'Decisão não encontrada.', 'INVALID_DECISION_ID');
  try {
    const { data } = await api.get<unknown>(`/investments/decisions/${encodeURIComponent(normalizedId)}/performance`, { signal });
    const normalized = normalizeInvestmentDecisionPerformance(data);
    if (normalized.decision_id !== normalizedId) throw invalidResponse('A performance retornada não corresponde à decisão solicitada.');
    return normalized;
  } catch (error) {
    throw normalizeApiError(error);
  }
}
