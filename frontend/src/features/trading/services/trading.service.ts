import { api } from '../../../services/api';
import type {
  PaperAccount,
  PaperEvent,
  PaperOrder,
  PaperOrderPayload,
  PaperPosition,
  TradingBacktest,
  TradingList,
  TradingModel,
  TradingOpportunity,
  TradingOverview,
} from '../types/trading.types';

export async function getTradingOverview(householdId: number, signal?: AbortSignal) {
  const { data } = await api.get<TradingOverview>('/trading/overview', {
    params: { household_id: householdId }, signal,
  });
  return data;
}

export async function createPaperAccount() {
  const { data } = await api.post<PaperAccount>('/trading/paper/account', {
    ownership_scope: 'PERSONAL', quote_asset: 'USDT', paper_only: true,
  });
  return data;
}

export async function getTradingOpportunities(signal?: AbortSignal) {
  const { data } = await api.get<TradingList<TradingOpportunity>>('/trading/opportunities', {
    params: { limit: 50, offset: 0 }, signal,
  });
  return data;
}

export async function getPaperOrders(signal?: AbortSignal) {
  const { data } = await api.get<TradingList<PaperOrder>>('/trading/paper/orders', {
    params: { limit: 50, offset: 0 }, signal,
  });
  return data;
}

export async function createPaperOrder(householdId: number, payload: PaperOrderPayload) {
  const { data } = await api.post<PaperOrder>('/trading/paper/orders', payload, {
    params: { household_id: householdId },
  });
  return data;
}

export async function cancelPaperOrder(orderId: number, idempotencyKey: string) {
  const { data } = await api.post<PaperOrder>(`/trading/paper/orders/${orderId}/cancel`, {
    idempotency_key: idempotencyKey, paper_only: true,
  });
  return data;
}

export async function getPaperPositions(signal?: AbortSignal) {
  const { data } = await api.get<TradingList<PaperPosition>>('/trading/paper/positions', {
    params: { limit: 50, offset: 0 }, signal,
  });
  return data;
}

export async function closePaperPosition(positionId: number, idempotencyKey: string) {
  const { data } = await api.post<PaperPosition>(`/trading/paper/positions/${positionId}/close`, {
    idempotency_key: idempotencyKey, paper_only: true,
  });
  return data;
}

export async function getPaperEvents(signal?: AbortSignal) {
  const { data } = await api.get<TradingList<PaperEvent>>('/trading/paper/events', {
    params: { limit: 100, offset: 0 }, signal,
  });
  return data;
}

export async function getTradingBacktests(signal?: AbortSignal) {
  const { data } = await api.get<TradingList<TradingBacktest>>('/trading/backtests', {
    params: { limit: 50, offset: 0 }, signal,
  });
  return data;
}

export async function getTradingModels(signal?: AbortSignal) {
  const { data } = await api.get<TradingList<TradingModel>>('/trading/models', {
    params: { limit: 100, offset: 0 }, signal,
  });
  return data;
}
