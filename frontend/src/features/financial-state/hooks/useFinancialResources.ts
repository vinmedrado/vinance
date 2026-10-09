import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useSessionToken } from '../../auth/hooks/useAuth';
import {
  createAsset,
  createExpense,
  createGoal,
  createIncome,
  createLiability,
  deleteAsset,
  deleteExpense,
  deleteGoal,
  deleteIncome,
  deleteLiability,
  listHouseholdAssets,
  listHouseholdExpenses,
  listHouseholdGoals,
  listHouseholdIncomes,
  listHouseholdLiabilities,
  updateAsset,
  updateExpense,
  updateGoal,
  updateIncome,
  updateLiability,
} from '../services/financialState.service';
import { financialStateQueryKey } from './useFinancialState';
import type {
  AssetPayload,
  AssetUpdatePayload,
  ExpensePayload,
  ExpenseUpdatePayload,
  GoalPayload,
  GoalUpdatePayload,
  HouseholdExpense,
  HouseholdGoal,
  HouseholdIncome,
  HouseholdLiability,
  HouseholdOwnedAsset,
  IncomePayload,
  IncomeUpdatePayload,
  LiabilityPayload,
  LiabilityUpdatePayload,
} from '../types/financialState.types';

export type FinancialResource = 'incomes' | 'expenses' | 'debts' | 'assets' | 'goals';
export type FinancialResourceItem = HouseholdIncome | HouseholdExpense | HouseholdLiability | HouseholdOwnedAsset | HouseholdGoal;
export type FinancialCreatePayload = IncomePayload | ExpensePayload | LiabilityPayload | AssetPayload | GoalPayload;
export type FinancialUpdatePayload = IncomeUpdatePayload | ExpenseUpdatePayload | LiabilityUpdatePayload | AssetUpdatePayload | GoalUpdatePayload;

type CreateRequest = {
  householdId: number;
  sessionToken: string | null;
  resource: FinancialResource;
  payload: FinancialCreatePayload;
};

type UpdateRequest = {
  householdId: number;
  sessionToken: string | null;
  resource: FinancialResource;
  recordId: number;
  payload: FinancialUpdatePayload;
};

type DeleteRequest = Omit<UpdateRequest, 'payload'>;

async function listResource(resource: FinancialResource, householdId: number, signal?: AbortSignal): Promise<FinancialResourceItem[]> {
  switch (resource) {
    case 'incomes': return await listHouseholdIncomes(householdId, signal);
    case 'expenses': return await listHouseholdExpenses(householdId, signal);
    case 'debts': return await listHouseholdLiabilities(householdId, signal);
    case 'assets': return await listHouseholdAssets(householdId, signal);
    case 'goals': return await listHouseholdGoals(householdId, signal);
  }
}

async function createResource(request: CreateRequest): Promise<FinancialResourceItem> {
  switch (request.resource) {
    case 'incomes': return await createIncome(request.householdId, request.payload as IncomePayload);
    case 'expenses': return await createExpense(request.householdId, request.payload as ExpensePayload);
    case 'debts': return await createLiability(request.householdId, request.payload as LiabilityPayload);
    case 'assets': return await createAsset(request.householdId, request.payload as AssetPayload);
    case 'goals': return await createGoal(request.householdId, request.payload as GoalPayload);
  }
}

async function updateResource(request: UpdateRequest): Promise<FinancialResourceItem> {
  switch (request.resource) {
    case 'incomes': return await updateIncome(request.householdId, request.recordId, request.payload as IncomeUpdatePayload);
    case 'expenses': return await updateExpense(request.householdId, request.recordId, request.payload as ExpenseUpdatePayload);
    case 'debts': return await updateLiability(request.householdId, request.recordId, request.payload as LiabilityUpdatePayload);
    case 'assets': return await updateAsset(request.householdId, request.recordId, request.payload as AssetUpdatePayload);
    case 'goals': return await updateGoal(request.householdId, request.recordId, request.payload as GoalUpdatePayload);
  }
}

function deleteResource(request: DeleteRequest) {
  switch (request.resource) {
    case 'incomes': return deleteIncome(request.householdId, request.recordId);
    case 'expenses': return deleteExpense(request.householdId, request.recordId);
    case 'debts': return deleteLiability(request.householdId, request.recordId);
    case 'assets': return deleteAsset(request.householdId, request.recordId);
    case 'goals': return deleteGoal(request.householdId, request.recordId);
  }
}

export function useFinancialResourceList(resource: FinancialResource, householdId: number | null) {
  const token = useSessionToken();
  return useQuery({
    queryKey: financialStateQueryKey(token, resource, householdId),
    queryFn: ({ signal }) => listResource(resource, householdId as number, signal),
    enabled: householdId !== null,
  });
}

function useInvalidateFinancialResource() {
  const client = useQueryClient();
  return (request: { sessionToken: string | null; householdId: number; resource: FinancialResource }) => {
    for (const key of [
      financialStateQueryKey(request.sessionToken, request.resource, request.householdId),
      financialStateQueryKey(request.sessionToken, 'current', request.householdId),
      ['financial-policy', request.sessionToken, 'current', request.householdId],
      ['capital-allocation', request.sessionToken, 'current', request.householdId],
      ['investment-orchestration', request.sessionToken, 'current', request.householdId],
      ['action-plan', request.sessionToken, 'current', request.householdId],
      ['continuous-autopilot', request.sessionToken, 'current', request.householdId],
    ]) client.invalidateQueries({ queryKey: key });
  };
}

function assertContext(requestToken: string | null, currentToken: string | null) {
  if (requestToken !== currentToken) throw new Error('A sessão mudou. Revise o formulário antes de salvar.');
}

export function useCreateFinancialResource() {
  const token = useSessionToken();
  const invalidate = useInvalidateFinancialResource();
  return useMutation({
    mutationFn: (request: CreateRequest) => {
      assertContext(request.sessionToken, token);
      return createResource(request);
    },
    onSuccess: (_data, request) => invalidate(request),
  });
}

export function useUpdateFinancialResource() {
  const token = useSessionToken();
  const invalidate = useInvalidateFinancialResource();
  return useMutation({
    mutationFn: (request: UpdateRequest) => {
      assertContext(request.sessionToken, token);
      return updateResource(request);
    },
    onSuccess: (_data, request) => invalidate(request),
  });
}

export function useDeleteFinancialResource() {
  const token = useSessionToken();
  const invalidate = useInvalidateFinancialResource();
  return useMutation({
    mutationFn: (request: DeleteRequest) => {
      assertContext(request.sessionToken, token);
      return deleteResource(request);
    },
    onSuccess: (_data, request) => invalidate(request),
  });
}
