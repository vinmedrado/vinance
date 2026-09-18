import { useRef } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useSessionToken } from '../../auth/hooks/useAuth';
import {
  createCapitalAllocationDecision,
  createFinancialPolicyDecision,
  createExpense,
  createFinancialStateSnapshot,
  createIncome,
  getCapitalAllocationDecision,
  getCapitalAllocationFromPolicy,
  getCapitalAllocationHistory,
  getCurrentCapitalAllocation,
  getCurrentFinancialPolicy,
  getCurrentFinancialState,
  getDefaultHousehold,
  getFinancialPolicyDecision,
  getFinancialPolicyHistory,
  getFinancialStateHistory,
  listHouseholdExpenses,
  listHouseholdIncomes,
  listHouseholds,
} from '../services/financialState.service';
import type { ExpensePayload, IncomePayload } from '../types/financialState.types';

type FinancialQueryPart = string | number | null;

export const financialStateQueryKey = (
  sessionToken: string | null,
  ...parts: FinancialQueryPart[]
) => ['financial-state', sessionToken, ...parts] as const;

export const financialPolicyQueryKey = (
  sessionToken: string | null,
  ...parts: FinancialQueryPart[]
) => ['financial-policy', sessionToken, ...parts] as const;

export const capitalAllocationQueryKey = (
  sessionToken: string | null,
  ...parts: FinancialQueryPart[]
) => ['capital-allocation', sessionToken, ...parts] as const;

export function useHouseholds() {
  const sessionToken = useSessionToken();
  return useQuery({
    queryKey: financialStateQueryKey(sessionToken, 'households'),
    queryFn: listHouseholds,
  });
}

export function useDefaultHousehold() {
  const sessionToken = useSessionToken();
  return useQuery({
    queryKey: financialStateQueryKey(sessionToken, 'household', 'default'),
    queryFn: getDefaultHousehold,
  });
}

export function useCurrentFinancialState(householdId: number | null) {
  const sessionToken = useSessionToken();
  return useQuery({
    queryKey: financialStateQueryKey(sessionToken, 'current', householdId),
    queryFn: () => getCurrentFinancialState(householdId as number),
    enabled: householdId !== null,
  });
}

export function useCurrentFinancialPolicy(householdId: number | null) {
  const sessionToken = useSessionToken();
  return useQuery({
    queryKey: financialPolicyQueryKey(sessionToken, 'current', householdId),
    queryFn: () => getCurrentFinancialPolicy(householdId as number),
    enabled: householdId !== null,
  });
}

export function useFinancialPolicyHistory(householdId: number | null) {
  const sessionToken = useSessionToken();
  return useQuery({
    queryKey: financialPolicyQueryKey(sessionToken, 'history', householdId),
    queryFn: () => getFinancialPolicyHistory(householdId as number),
    enabled: householdId !== null,
  });
}

export function useFinancialPolicyDecision(
  householdId: number | null,
  policyId: number | null,
) {
  const sessionToken = useSessionToken();
  return useQuery({
    queryKey: financialPolicyQueryKey(sessionToken, 'history', householdId, policyId),
    queryFn: () => getFinancialPolicyDecision(householdId as number, policyId as number),
    enabled: householdId !== null && policyId !== null,
  });
}

export function useCurrentCapitalAllocation(householdId: number | null) {
  const sessionToken = useSessionToken();
  return useQuery({
    queryKey: capitalAllocationQueryKey(sessionToken, 'current', householdId),
    queryFn: () => getCurrentCapitalAllocation(householdId as number),
    enabled: householdId !== null,
  });
}

export function useCapitalAllocationFromPolicy(
  householdId: number | null,
  policyId: number | null,
) {
  const sessionToken = useSessionToken();
  return useQuery({
    queryKey: capitalAllocationQueryKey(sessionToken, 'policy', householdId, policyId),
    queryFn: () => getCapitalAllocationFromPolicy(
      householdId as number,
      policyId as number,
    ),
    enabled: householdId !== null && policyId !== null,
  });
}

export function useCapitalAllocationHistory(householdId: number | null) {
  const sessionToken = useSessionToken();
  return useQuery({
    queryKey: capitalAllocationQueryKey(sessionToken, 'history', householdId),
    queryFn: () => getCapitalAllocationHistory(householdId as number),
    enabled: householdId !== null,
  });
}

export function useCapitalAllocationDecision(
  householdId: number | null,
  allocationId: number | null,
) {
  const sessionToken = useSessionToken();
  return useQuery({
    queryKey: capitalAllocationQueryKey(
      sessionToken,
      'history',
      householdId,
      allocationId,
    ),
    queryFn: () => getCapitalAllocationDecision(
      householdId as number,
      allocationId as number,
    ),
    enabled: householdId !== null && allocationId !== null,
  });
}

export function useFinancialStateHistory(householdId: number | null) {
  const sessionToken = useSessionToken();
  return useQuery({
    queryKey: financialStateQueryKey(sessionToken, 'history', householdId),
    queryFn: () => getFinancialStateHistory(householdId as number),
    enabled: householdId !== null,
  });
}

export function useHouseholdIncomes(householdId: number | null) {
  const sessionToken = useSessionToken();
  return useQuery({
    queryKey: financialStateQueryKey(sessionToken, 'incomes', householdId),
    queryFn: () => listHouseholdIncomes(householdId as number),
    enabled: householdId !== null,
  });
}

export function useHouseholdExpenses(householdId: number | null) {
  const sessionToken = useSessionToken();
  return useQuery({
    queryKey: financialStateQueryKey(sessionToken, 'expenses', householdId),
    queryFn: () => listHouseholdExpenses(householdId as number),
    enabled: householdId !== null,
  });
}

export function useCreateHouseholdIncome(householdId: number | null) {
  const queryClient = useQueryClient();
  const sessionToken = useSessionToken();
  return useMutation({
    mutationFn: (payload: IncomePayload) => {
      if (householdId === null) throw new Error('Household não selecionado');
      return createIncome(householdId, payload);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: financialStateQueryKey(sessionToken, 'incomes', householdId) });
      queryClient.invalidateQueries({ queryKey: financialStateQueryKey(sessionToken, 'current', householdId) });
      queryClient.invalidateQueries({ queryKey: financialPolicyQueryKey(sessionToken, 'current', householdId) });
      queryClient.invalidateQueries({ queryKey: capitalAllocationQueryKey(sessionToken, 'current', householdId) });
      queryClient.invalidateQueries({ queryKey: ['financial'] });
    },
  });
}

export function useCreateHouseholdExpense(householdId: number | null) {
  const queryClient = useQueryClient();
  const sessionToken = useSessionToken();
  return useMutation({
    mutationFn: (payload: ExpensePayload) => {
      if (householdId === null) throw new Error('Household não selecionado');
      return createExpense(householdId, payload);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: financialStateQueryKey(sessionToken, 'expenses', householdId) });
      queryClient.invalidateQueries({ queryKey: financialStateQueryKey(sessionToken, 'current', householdId) });
      queryClient.invalidateQueries({ queryKey: financialPolicyQueryKey(sessionToken, 'current', householdId) });
      queryClient.invalidateQueries({ queryKey: capitalAllocationQueryKey(sessionToken, 'current', householdId) });
      queryClient.invalidateQueries({ queryKey: ['financial'] });
    },
  });
}

function snapshotIdempotencyKey(householdId: number) {
  const randomPart = globalThis.crypto?.randomUUID?.()
    ?? `${Date.now()}-${Math.random().toString(16).slice(2)}`;
  return `financial-state-${householdId}-${randomPart}`;
}

function policyIdempotencyKey(householdId: number) {
  const randomPart = globalThis.crypto?.randomUUID?.()
    ?? `${Date.now()}-${Math.random().toString(16).slice(2)}`;
  return `financial-policy-${householdId}-${randomPart}`;
}

function allocationIdempotencyKey(householdId: number) {
  const randomPart = globalThis.crypto?.randomUUID?.()
    ?? `${Date.now()}-${Math.random().toString(16).slice(2)}`;
  return `capital-allocation-${householdId}-${randomPart}`;
}

export function useCreateFinancialPolicyDecision(householdId: number | null) {
  const queryClient = useQueryClient();
  const sessionToken = useSessionToken();
  const pendingRequest = useRef<{
    householdId: number;
    key: string;
    sessionToken: string | null;
  } | null>(null);
  return useMutation({
    mutationFn: () => {
      if (householdId === null) throw new Error('Household não selecionado');
      if (!pendingRequest.current || pendingRequest.current.householdId !== householdId) {
        pendingRequest.current = {
          householdId,
          key: policyIdempotencyKey(householdId),
          sessionToken,
        };
      }
      return createFinancialPolicyDecision(householdId, pendingRequest.current.key);
    },
    onSuccess: (decision) => {
      const completedRequest = pendingRequest.current;
      pendingRequest.current = null;
      const completedHouseholdId = decision.household_id;
      const completedSessionToken = completedRequest?.householdId === completedHouseholdId
        ? completedRequest.sessionToken
        : sessionToken;
      queryClient.setQueryData(
        financialPolicyQueryKey(
          completedSessionToken,
          'history',
          completedHouseholdId,
          decision.policy_id,
        ),
        decision,
      );
      queryClient.invalidateQueries({
        queryKey: financialPolicyQueryKey(
          completedSessionToken,
          'history',
          completedHouseholdId,
        ),
      });
      queryClient.invalidateQueries({
        queryKey: financialPolicyQueryKey(
          completedSessionToken,
          'current',
          completedHouseholdId,
        ),
      });
    },
  });
}

export function useCreateCapitalAllocationDecision(householdId: number | null) {
  const queryClient = useQueryClient();
  const sessionToken = useSessionToken();
  const pendingRequest = useRef<{
    householdId: number;
    key: string;
    sessionToken: string | null;
  } | null>(null);
  return useMutation({
    mutationFn: () => {
      if (householdId === null) throw new Error('Household não selecionado');
      if (!pendingRequest.current || pendingRequest.current.householdId !== householdId) {
        pendingRequest.current = {
          householdId,
          key: allocationIdempotencyKey(householdId),
          sessionToken,
        };
      }
      return createCapitalAllocationDecision(householdId, pendingRequest.current.key);
    },
    onSuccess: (decision) => {
      const completedRequest = pendingRequest.current;
      pendingRequest.current = null;
      const completedHouseholdId = decision.household_id;
      const completedSessionToken = completedRequest?.householdId === completedHouseholdId
        ? completedRequest.sessionToken
        : sessionToken;
      queryClient.setQueryData(
        capitalAllocationQueryKey(
          completedSessionToken,
          'history',
          completedHouseholdId,
          decision.allocation_id,
        ),
        decision,
      );
      queryClient.invalidateQueries({
        queryKey: capitalAllocationQueryKey(
          completedSessionToken,
          'history',
          completedHouseholdId,
        ),
      });
      queryClient.invalidateQueries({
        queryKey: capitalAllocationQueryKey(
          completedSessionToken,
          'current',
          completedHouseholdId,
        ),
      });
      queryClient.invalidateQueries({
        queryKey: financialPolicyQueryKey(
          completedSessionToken,
          'history',
          completedHouseholdId,
        ),
      });
      queryClient.invalidateQueries({
        queryKey: financialPolicyQueryKey(
          completedSessionToken,
          'current',
          completedHouseholdId,
        ),
      });
      queryClient.invalidateQueries({
        queryKey: financialStateQueryKey(
          completedSessionToken,
          'history',
          completedHouseholdId,
        ),
      });
      queryClient.invalidateQueries({
        queryKey: financialStateQueryKey(
          completedSessionToken,
          'current',
          completedHouseholdId,
        ),
      });
    },
  });
}

export function useCreateFinancialStateSnapshot(householdId: number | null) {
  const queryClient = useQueryClient();
  const sessionToken = useSessionToken();
  const pendingRequest = useRef<{ householdId: number; key: string } | null>(null);
  return useMutation({
    mutationFn: () => {
      if (householdId === null) throw new Error('Household não selecionado');
      if (!pendingRequest.current || pendingRequest.current.householdId !== householdId) {
        pendingRequest.current = { householdId, key: snapshotIdempotencyKey(householdId) };
      }
      return createFinancialStateSnapshot(householdId, pendingRequest.current.key);
    },
    onSuccess: () => {
      pendingRequest.current = null;
      queryClient.invalidateQueries({ queryKey: financialStateQueryKey(sessionToken, 'history', householdId) });
      queryClient.invalidateQueries({ queryKey: financialPolicyQueryKey(sessionToken, 'current', householdId) });
      queryClient.invalidateQueries({ queryKey: capitalAllocationQueryKey(sessionToken, 'current', householdId) });
    },
  });
}
