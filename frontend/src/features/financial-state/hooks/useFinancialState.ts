import { useRef } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  createExpense,
  createFinancialStateSnapshot,
  createIncome,
  getCurrentFinancialState,
  getDefaultHousehold,
  getFinancialStateHistory,
  listHouseholdExpenses,
  listHouseholdIncomes,
  listHouseholds,
} from '../services/financialState.service';
import type { ExpensePayload, IncomePayload } from '../types/financialState.types';

export function useHouseholds() {
  return useQuery({ queryKey: ['financial-state', 'households'], queryFn: listHouseholds });
}

export function useDefaultHousehold() {
  return useQuery({ queryKey: ['financial-state', 'household', 'default'], queryFn: getDefaultHousehold });
}

export function useCurrentFinancialState(householdId: number | null) {
  return useQuery({
    queryKey: ['financial-state', 'current', householdId],
    queryFn: () => getCurrentFinancialState(householdId as number),
    enabled: householdId !== null,
  });
}

export function useFinancialStateHistory(householdId: number | null) {
  return useQuery({
    queryKey: ['financial-state', 'history', householdId],
    queryFn: () => getFinancialStateHistory(householdId as number),
    enabled: householdId !== null,
  });
}

export function useHouseholdIncomes(householdId: number | null) {
  return useQuery({
    queryKey: ['financial-state', 'incomes', householdId],
    queryFn: () => listHouseholdIncomes(householdId as number),
    enabled: householdId !== null,
  });
}

export function useHouseholdExpenses(householdId: number | null) {
  return useQuery({
    queryKey: ['financial-state', 'expenses', householdId],
    queryFn: () => listHouseholdExpenses(householdId as number),
    enabled: householdId !== null,
  });
}

export function useCreateHouseholdIncome(householdId: number | null) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: IncomePayload) => {
      if (householdId === null) throw new Error('Household não selecionado');
      return createIncome(householdId, payload);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['financial-state', 'incomes', householdId] });
      queryClient.invalidateQueries({ queryKey: ['financial-state', 'current', householdId] });
      queryClient.invalidateQueries({ queryKey: ['financial'] });
    },
  });
}

export function useCreateHouseholdExpense(householdId: number | null) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: ExpensePayload) => {
      if (householdId === null) throw new Error('Household não selecionado');
      return createExpense(householdId, payload);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['financial-state', 'expenses', householdId] });
      queryClient.invalidateQueries({ queryKey: ['financial-state', 'current', householdId] });
      queryClient.invalidateQueries({ queryKey: ['financial'] });
    },
  });
}

function snapshotIdempotencyKey(householdId: number) {
  const randomPart = globalThis.crypto?.randomUUID?.()
    ?? `${Date.now()}-${Math.random().toString(16).slice(2)}`;
  return `financial-state-${householdId}-${randomPart}`;
}

export function useCreateFinancialStateSnapshot(householdId: number | null) {
  const queryClient = useQueryClient();
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
      queryClient.invalidateQueries({ queryKey: ['financial-state', 'history', householdId] });
    },
  });
}
