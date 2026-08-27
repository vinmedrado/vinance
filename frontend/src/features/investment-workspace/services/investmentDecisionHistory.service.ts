import { api, ApiRequestError, normalizeApiError } from '../../../services/api';
import type {
  InvestmentDecisionDetail,
  InvestmentDecisionHistoryItem,
  InvestmentDecisionHistoryPage,
} from '../types/investmentWorkspace.types';

const HISTORY_ENDPOINT = '/investments/decisions';
const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

function invalidResponse(message: string) {
  return new ApiRequestError(502, message, 'INVALID_RESPONSE');
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function stringValue(value: unknown) {
  return typeof value === 'string' && value.trim() ? value.trim() : undefined;
}

function uuidValue(value: unknown) {
  const normalized = stringValue(value);
  return normalized && UUID_PATTERN.test(normalized) ? normalized.toLowerCase() : undefined;
}

function isoDate(value: unknown) {
  const normalized = stringValue(value);
  if (!normalized || !Number.isFinite(Date.parse(normalized))) return undefined;
  return new Date(normalized).toISOString();
}

function finiteNumber(value: unknown) {
  const number = Number(value);
  return Number.isFinite(number) ? number : undefined;
}

function numberLike(value: unknown) {
  const number = finiteNumber(value);
  if (number === undefined) return undefined;
  return typeof value === 'string' ? value.trim() : number;
}

function nullableString(value: unknown) {
  return value === null ? null : stringValue(value);
}

function nullableNumberLike(value: unknown) {
  return value === null ? null : numberLike(value);
}

function historyItem(value: unknown): InvestmentDecisionHistoryItem | null {
  if (!isRecord(value)) return null;
  const decisionId = uuidValue(value.decision_id);
  const correlationId = uuidValue(value.correlation_id);
  const createdAt = isoDate(value.created_at);
  const budget = numberLike(value.budget);
  const recommendation = stringValue(value.recommendation);
  const status = stringValue(value.status);
  const latency = finiteNumber(value.latency_ms);
  if (!decisionId || !correlationId || !createdAt || budget === undefined || !recommendation || !status || latency === undefined) return null;

  return {
    decision_id: decisionId,
    correlation_id: correlationId,
    created_at: createdAt,
    asset: nullableString(value.asset),
    market: nullableString(value.market),
    budget,
    investor_profile: nullableString(value.investor_profile),
    recommendation,
    quantity: value.quantity === null ? null : finiteNumber(value.quantity),
    price: nullableNumberLike(value.price),
    invested_amount: nullableNumberLike(value.invested_amount),
    remaining_amount: nullableNumberLike(value.remaining_amount),
    risk_level: nullableString(value.risk_level),
    confidence: nullableNumberLike(value.confidence),
    trend: nullableString(value.trend),
    ranking: value.ranking === null ? null : finiteNumber(value.ranking),
    recommendation_score: nullableNumberLike(value.recommendation_score),
    guardrail_status: nullableString(value.guardrail_status),
    latency_ms: Math.max(0, Math.round(latency)),
    fallback_used: value.fallback_used === true,
    error_code: nullableString(value.error_code),
    status,
  };
}

export function normalizeDecisionHistoryResponse(value: unknown): InvestmentDecisionHistoryPage {
  if (!isRecord(value) || !Array.isArray(value.items)) throw invalidResponse('A API retornou um histórico de decisões inválido.');
  const page = finiteNumber(value.page);
  const pageSize = finiteNumber(value.page_size);
  const total = finiteNumber(value.total);
  const totalPages = finiteNumber(value.total_pages);
  if ([page, pageSize, total, totalPages].some((item) => item === undefined || item < 0)) {
    throw invalidResponse('A paginação do histórico de decisões é inválida.');
  }
  const items = value.items.map(historyItem).filter((item): item is InvestmentDecisionHistoryItem => item !== null);
  return {
    items,
    page: Math.max(1, Math.trunc(page!)),
    page_size: Math.max(1, Math.trunc(pageSize!)),
    total: Math.trunc(total!),
    total_pages: Math.trunc(totalPages!),
  };
}

export function normalizeDecisionDetailResponse(value: unknown): InvestmentDecisionDetail {
  const summary = historyItem(value);
  if (!summary || !isRecord(value)) throw invalidResponse('A API retornou um detalhe de decisão inválido.');
  const requiredRecords = ['guardrail_reasons', 'explanation', 'request_parameters', 'input_snapshot', 'score_snapshot', 'response_snapshot'] as const;
  if (requiredRecords.some((key) => !isRecord(value[key]))) throw invalidResponse('O snapshot auditável da decisão está incompleto.');
  const snapshotSchemaVersion = stringValue(value.snapshot_schema_version);
  const ruleVersion = stringValue(value.rule_version);
  const engineVersion = stringValue(value.recommendation_engine_version);
  if (!snapshotSchemaVersion || !ruleVersion || !engineVersion) throw invalidResponse('O versionamento da decisão está incompleto.');

  return {
    ...summary,
    guardrail_reasons: value.guardrail_reasons as Record<string, unknown>,
    explanation: value.explanation as Record<string, unknown>,
    request_parameters: value.request_parameters as Record<string, unknown>,
    input_snapshot: value.input_snapshot as Record<string, unknown>,
    score_snapshot: value.score_snapshot as Record<string, unknown>,
    response_snapshot: value.response_snapshot as Record<string, unknown>,
    snapshot_schema_version: snapshotSchemaVersion,
    rule_version: ruleVersion,
    recommendation_engine_version: engineVersion,
    score_version: nullableString(value.score_version),
    guardrail_version: nullableString(value.guardrail_version),
    trend_version: nullableString(value.trend_version),
  };
}

export async function getInvestmentDecisionHistory(page = 1, pageSize = 10, signal?: AbortSignal) {
  try {
    const { data } = await api.get<unknown>(HISTORY_ENDPOINT, { signal, params: { page, page_size: pageSize } });
    return normalizeDecisionHistoryResponse(data);
  } catch (error) {
    const normalized = normalizeApiError(error);
    if (normalized.code !== 'REQUEST_CANCELED') {
      console.error('[Vinance][investment-history] Falha ao carregar o histórico.', {
        code: normalized.code,
        status: normalized.status,
        correlationId: normalized.correlationId,
      });
    }
    throw normalized;
  }
}

export async function getInvestmentDecisionDetail(decisionId: string, signal?: AbortSignal) {
  const normalizedId = uuidValue(decisionId);
  if (!normalizedId) throw new ApiRequestError(404, 'Decisão não encontrada.', 'INVALID_DECISION_ID');
  try {
    const { data } = await api.get<unknown>(`${HISTORY_ENDPOINT}/${encodeURIComponent(normalizedId)}`, { signal });
    const detail = normalizeDecisionDetailResponse(data);
    if (detail.decision_id !== normalizedId) throw invalidResponse('O detalhe retornado não corresponde à decisão solicitada.');
    return detail;
  } catch (error) {
    throw normalizeApiError(error);
  }
}
