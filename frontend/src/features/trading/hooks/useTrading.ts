import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useSessionToken } from '../../auth/hooks/useAuth';
import {
  cancelPaperOrder,
  closePaperPosition,
  createPaperAccount,
  createPaperOrder,
  getPaperEvents,
  getPaperOrders,
  getPaperPositions,
  getTradingBacktests,
  getTradingModels,
  getTradingOpportunities,
  getTradingOverview,
} from '../services/trading.service';
import type { PaperOrderPayload } from '../types/trading.types';

const key = (token: string | null, ...parts: Array<string | number | null>) => ['trading', token, ...parts] as const;

export function useTradingOverview(householdId: number | null) {
  const token = useSessionToken();
  return useQuery({
    queryKey: key(token, 'overview', householdId),
    queryFn: ({ signal }) => getTradingOverview(householdId as number, signal),
    enabled: householdId !== null,
  });
}

export function useTradingOpportunities(enabled: boolean) {
  const token = useSessionToken();
  return useQuery({ queryKey: key(token, 'opportunities'), queryFn: ({ signal }) => getTradingOpportunities(signal), enabled });
}

export function usePaperOrders(enabled: boolean) {
  const token = useSessionToken();
  return useQuery({ queryKey: key(token, 'orders'), queryFn: ({ signal }) => getPaperOrders(signal), enabled });
}

export function usePaperPositions(enabled: boolean) {
  const token = useSessionToken();
  return useQuery({ queryKey: key(token, 'positions'), queryFn: ({ signal }) => getPaperPositions(signal), enabled });
}

export function usePaperEvents(enabled: boolean) {
  const token = useSessionToken();
  return useQuery({ queryKey: key(token, 'events'), queryFn: ({ signal }) => getPaperEvents(signal), enabled });
}

export function useTradingBacktests(enabled: boolean) {
  const token = useSessionToken();
  return useQuery({ queryKey: key(token, 'backtests'), queryFn: ({ signal }) => getTradingBacktests(signal), enabled });
}

export function useTradingModels(enabled: boolean) {
  const token = useSessionToken();
  return useQuery({ queryKey: key(token, 'models'), queryFn: ({ signal }) => getTradingModels(signal), enabled });
}

export function useTradingMutations() {
  const token = useSessionToken();
  const client = useQueryClient();
  const invalidate = () => client.invalidateQueries({ queryKey: key(token) });
  return {
    createAccount: useMutation({ mutationFn: createPaperAccount, onSuccess: invalidate }),
    createOrder: useMutation({
      mutationFn: ({ householdId, payload }: { householdId: number; payload: PaperOrderPayload }) => createPaperOrder(householdId, payload),
      onSuccess: invalidate,
    }),
    cancelOrder: useMutation({
      mutationFn: ({ orderId, idempotencyKey }: { orderId: number; idempotencyKey: string }) => cancelPaperOrder(orderId, idempotencyKey),
      onSuccess: invalidate,
    }),
    closePosition: useMutation({
      mutationFn: ({ positionId, idempotencyKey }: { positionId: number; idempotencyKey: string }) => closePaperPosition(positionId, idempotencyKey),
      onSuccess: invalidate,
    }),
  };
}
