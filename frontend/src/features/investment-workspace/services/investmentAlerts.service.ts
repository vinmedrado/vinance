import { api, ApiRequestError, normalizeApiError } from '../../../services/api';
import type {
  InvestmentAlertDetail,
  InvestmentAlertItem,
  InvestmentAlertsFilters,
  InvestmentAlertsPage,
  InvestmentAlertSeverity,
  InvestmentAlertState,
  InvestmentAlertSubscription,
  InvestmentAlertSubscriptionCreate,
  InvestmentAlertSubscriptionList,
  InvestmentAlertSubscriptionUpdate,
  InvestmentAlertType,
} from '../types/investmentWorkspace.types';

const SUBSCRIPTIONS_ENDPOINT = '/investments/alert-subscriptions';
const ALERTS_ENDPOINT = '/investments/alerts';
const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
const ASSET_PATTERN = /^[A-Z0-9.-]{1,32}$/;
const ALERT_TYPES = new Set<InvestmentAlertType>([
  'NEW_OPPORTUNITY',
  'ACTION_CHANGE',
  'SCORE_CHANGE',
  'CONFIDENCE_CHANGE',
  'RISK_CHANGE',
]);
const ALERT_SEVERITIES = new Set<InvestmentAlertSeverity>(['INFO', 'MEDIUM', 'HIGH']);

function invalidResponse(message: string) {
  return new ApiRequestError(502, message, 'INVALID_RESPONSE');
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function textValue(value: unknown) {
  return typeof value === 'string' && value.trim() ? value.trim() : undefined;
}

function uuidValue(value: unknown) {
  const normalized = textValue(value);
  return normalized && UUID_PATTERN.test(normalized) ? normalized.toLowerCase() : undefined;
}

function isoDate(value: unknown) {
  const normalized = textValue(value);
  if (!normalized || !Number.isFinite(Date.parse(normalized))) return undefined;
  return new Date(normalized).toISOString();
}

function finiteNumber(value: unknown) {
  if (value === null || value === undefined || value === '') return undefined;
  const normalized = Number(value);
  return Number.isFinite(normalized) ? normalized : undefined;
}

function nonNegativeInteger(value: unknown) {
  const normalized = finiteNumber(value);
  return normalized !== undefined && normalized >= 0 && Number.isInteger(normalized) ? normalized : undefined;
}

function positiveInteger(value: unknown) {
  const normalized = nonNegativeInteger(value);
  return normalized !== undefined && normalized > 0 ? normalized : undefined;
}

function booleanValue(value: unknown) {
  return typeof value === 'boolean' ? value : undefined;
}

function assetValue(value: unknown) {
  const normalized = textValue(value)?.toUpperCase();
  return normalized && ASSET_PATTERN.test(normalized) ? normalized : undefined;
}

function alertTypeValue(value: unknown) {
  const normalized = textValue(value)?.toUpperCase() as InvestmentAlertType | undefined;
  return normalized && ALERT_TYPES.has(normalized) ? normalized : undefined;
}

function alertSeverityValue(value: unknown) {
  const normalized = textValue(value)?.toUpperCase() as InvestmentAlertSeverity | undefined;
  return normalized && ALERT_SEVERITIES.has(normalized) ? normalized : undefined;
}

function normalizeSubscription(value: unknown): InvestmentAlertSubscription {
  if (!isRecord(value)) throw invalidResponse('A API retornou um monitoramento inválido.');
  const id = positiveInteger(value.id);
  const asset = assetValue(value.asset);
  const market = textValue(value.market);
  const budget = finiteNumber(value.budget);
  const investorProfile = textValue(value.investor_profile);
  const sourceDecisionId = uuidValue(value.source_decision_id);
  const ruleVersion = textValue(value.rule_version);
  const createdAt = isoDate(value.created_at);
  const updatedAt = isoDate(value.updated_at);
  const minimumScoreDelta = finiteNumber(value.minimum_score_delta);
  const minimumConfidenceDelta = finiteNumber(value.minimum_confidence_delta);
  const cooldownMinutes = positiveInteger(value.cooldown_minutes);
  const flags = {
    enabled: booleanValue(value.enabled),
    alert_on_action_change: booleanValue(value.alert_on_action_change),
    alert_on_score_change: booleanValue(value.alert_on_score_change),
    alert_on_confidence_change: booleanValue(value.alert_on_confidence_change),
    alert_on_risk_change: booleanValue(value.alert_on_risk_change),
    alert_on_new_opportunity: booleanValue(value.alert_on_new_opportunity),
  };

  if (
    id === undefined
    || !asset
    || !market
    || budget === undefined
    || budget <= 0
    || !investorProfile
    || !sourceDecisionId
    || !ruleVersion
    || !createdAt
    || !updatedAt
    || minimumScoreDelta === undefined
    || minimumScoreDelta < 0
    || minimumConfidenceDelta === undefined
    || minimumConfidenceDelta < 0
    || cooldownMinutes === undefined
    || Object.values(flags).some((item) => item === undefined)
  ) {
    throw invalidResponse('A API retornou um monitoramento incompleto.');
  }

  return {
    id,
    asset,
    market,
    budget,
    investor_profile: investorProfile,
    source_decision_id: sourceDecisionId,
    enabled: flags.enabled!,
    alert_on_action_change: flags.alert_on_action_change!,
    alert_on_score_change: flags.alert_on_score_change!,
    alert_on_confidence_change: flags.alert_on_confidence_change!,
    alert_on_risk_change: flags.alert_on_risk_change!,
    alert_on_new_opportunity: flags.alert_on_new_opportunity!,
    minimum_score_delta: minimumScoreDelta,
    minimum_confidence_delta: minimumConfidenceDelta,
    cooldown_minutes: cooldownMinutes,
    rule_version: ruleVersion,
    created_at: createdAt,
    updated_at: updatedAt,
  };
}

export function normalizeInvestmentAlertSubscriptions(value: unknown): InvestmentAlertSubscriptionList {
  if (!isRecord(value) || !Array.isArray(value.items)) {
    throw invalidResponse('A API retornou uma lista de monitoramentos inválida.');
  }
  const total = nonNegativeInteger(value.total);
  const active = nonNegativeInteger(value.active);
  const limit = positiveInteger(value.limit);
  if (total === undefined || active === undefined || limit === undefined || active > total) {
    throw invalidResponse('Os totais de monitoramento retornados pela API são inválidos.');
  }
  const items = value.items.map(normalizeSubscription);
  if (items.length > total) throw invalidResponse('A lista de monitoramentos é inconsistente.');
  return { items, total, active, limit };
}

function normalizeAlertItem(value: unknown): InvestmentAlertItem {
  if (!isRecord(value)) throw invalidResponse('A API retornou um alerta inválido.');
  const alertId = uuidValue(value.alert_id);
  const decisionId = uuidValue(value.decision_id);
  const subscriptionId = value.subscription_id === null ? null : positiveInteger(value.subscription_id);
  const asset = assetValue(value.asset);
  const alertType = alertTypeValue(value.alert_type);
  const severity = alertSeverityValue(value.severity);
  const deliveryChannel = textValue(value.delivery_channel)?.toUpperCase();
  const message = textValue(value.message);
  const createdAt = isoDate(value.created_at);
  const readAt = value.read_at === null ? null : isoDate(value.read_at);

  if (
    !alertId
    || !decisionId
    || (value.subscription_id !== null && subscriptionId === undefined)
    || !asset
    || !alertType
    || !severity
    || deliveryChannel !== 'IN_APP'
    || !message
    || !createdAt
    || (value.read_at !== null && !readAt)
  ) {
    throw invalidResponse('A API retornou um alerta incompleto.');
  }

  return {
    alert_id: alertId,
    subscription_id: subscriptionId,
    decision_id: decisionId,
    asset,
    alert_type: alertType,
    severity,
    delivery_channel: 'IN_APP',
    message,
    created_at: createdAt,
    read_at: readAt,
  };
}

export function normalizeInvestmentAlertsPage(value: unknown): InvestmentAlertsPage {
  if (!isRecord(value) || !Array.isArray(value.items)) throw invalidResponse('A API retornou uma central de alertas inválida.');
  const page = positiveInteger(value.page);
  const pageSize = positiveInteger(value.page_size);
  const total = nonNegativeInteger(value.total);
  const totalPages = nonNegativeInteger(value.total_pages);
  const unreadCount = nonNegativeInteger(value.unread_count);
  if (page === undefined || pageSize === undefined || total === undefined || totalPages === undefined || unreadCount === undefined) {
    throw invalidResponse('A paginação da central de alertas é inválida.');
  }
  const items = value.items.map(normalizeAlertItem);
  if (items.length > pageSize || unreadCount > total) throw invalidResponse('A central de alertas retornou totais inconsistentes.');
  return { items, page, page_size: pageSize, total, total_pages: totalPages, unread_count: unreadCount };
}

export function normalizeInvestmentAlertDetail(value: unknown): InvestmentAlertDetail {
  const item = normalizeAlertItem(value);
  if (!isRecord(value) || !isRecord(value.previous_state) || !isRecord(value.current_state)) {
    throw invalidResponse('O contexto comparativo do alerta está incompleto.');
  }
  const ruleVersion = textValue(value.rule_version);
  if (!ruleVersion) throw invalidResponse('O alerta não informou a versão da regra utilizada.');
  return {
    ...item,
    previous_state: value.previous_state as InvestmentAlertState,
    current_state: value.current_state as InvestmentAlertState,
    rule_version: ruleVersion,
  };
}

function safeAsset(value: string) {
  const normalized = assetValue(value);
  if (!normalized) throw new ApiRequestError(400, 'Informe um ticker válido para monitoramento.', 'INVALID_ASSET');
  return normalized;
}

function safeUuid(value: string, label: string) {
  const normalized = uuidValue(value);
  if (!normalized) throw new ApiRequestError(404, `${label} não encontrado.`, 'INVALID_ID');
  return normalized;
}

export async function getInvestmentAlertSubscriptions(signal?: AbortSignal) {
  try {
    const { data } = await api.get<unknown>(SUBSCRIPTIONS_ENDPOINT, { signal });
    return normalizeInvestmentAlertSubscriptions(data);
  } catch (error) {
    throw normalizeApiError(error);
  }
}

export async function createInvestmentAlertSubscription(payload: InvestmentAlertSubscriptionCreate) {
  const request = {
    asset: safeAsset(payload.asset),
    source_decision_id: safeUuid(payload.source_decision_id, 'Decisão'),
  };
  try {
    const { data } = await api.post<unknown>(SUBSCRIPTIONS_ENDPOINT, request);
    return normalizeSubscription(data);
  } catch (error) {
    throw normalizeApiError(error);
  }
}

export async function updateInvestmentAlertSubscription(id: number, payload: InvestmentAlertSubscriptionUpdate) {
  if (!Number.isInteger(id) || id <= 0) throw new ApiRequestError(404, 'Monitoramento não encontrado.', 'INVALID_ID');
  try {
    const { data } = await api.patch<unknown>(`${SUBSCRIPTIONS_ENDPOINT}/${id}`, payload);
    return normalizeSubscription(data);
  } catch (error) {
    throw normalizeApiError(error);
  }
}

export async function deleteInvestmentAlertSubscription(id: number) {
  if (!Number.isInteger(id) || id <= 0) throw new ApiRequestError(404, 'Monitoramento não encontrado.', 'INVALID_ID');
  try {
    await api.delete(`${SUBSCRIPTIONS_ENDPOINT}/${id}`);
  } catch (error) {
    throw normalizeApiError(error);
  }
}

export async function getInvestmentAlerts(filters: InvestmentAlertsFilters = {}, signal?: AbortSignal) {
  try {
    const { data } = await api.get<unknown>(ALERTS_ENDPOINT, {
      signal,
      params: {
        page: filters.page ?? 1,
        page_size: filters.pageSize ?? 10,
        asset: filters.asset ? safeAsset(filters.asset) : undefined,
        alert_type: filters.alertType || undefined,
        severity: filters.severity || undefined,
        unread_only: filters.unreadOnly || undefined,
        date_from: filters.dateFrom || undefined,
        date_to: filters.dateTo || undefined,
      },
    });
    return normalizeInvestmentAlertsPage(data);
  } catch (error) {
    throw normalizeApiError(error);
  }
}

export async function getInvestmentAlertDetail(alertId: string, signal?: AbortSignal) {
  const normalizedId = safeUuid(alertId, 'Alerta');
  try {
    const { data } = await api.get<unknown>(`${ALERTS_ENDPOINT}/${encodeURIComponent(normalizedId)}`, { signal });
    const detail = normalizeInvestmentAlertDetail(data);
    if (detail.alert_id !== normalizedId) throw invalidResponse('O detalhe retornado não corresponde ao alerta solicitado.');
    return detail;
  } catch (error) {
    throw normalizeApiError(error);
  }
}

export async function markInvestmentAlertRead(alertId: string) {
  const normalizedId = safeUuid(alertId, 'Alerta');
  try {
    const { data } = await api.patch<unknown>(`${ALERTS_ENDPOINT}/${encodeURIComponent(normalizedId)}/read`, {});
    const item = normalizeAlertItem(data);
    if (item.alert_id !== normalizedId) throw invalidResponse('A confirmação de leitura não corresponde ao alerta solicitado.');
    return item;
  } catch (error) {
    throw normalizeApiError(error);
  }
}
