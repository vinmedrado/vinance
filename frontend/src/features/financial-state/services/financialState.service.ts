import { api } from '../../../services/api';
import type {
  AssetPayload,
  CapitalAllocation,
  CapitalAllocationHistory,
  ExpensePayload,
  FinancialState,
  FinancialStateHistory,
  FinancialPolicy,
  FinancialPolicyHistory,
  FinancialStateSnapshot,
  GoalPayload,
  Household,
  HouseholdExpense,
  HouseholdIncome,
  IncomePayload,
  LiabilityPayload,
} from '../types/financialState.types';

export async function listHouseholds() {
  const { data } = await api.get<Household[]>('/financial/households');
  return data;
}

export async function getDefaultHousehold() {
  const { data } = await api.get<Household>('/financial/households/default');
  return data;
}

export async function getCurrentFinancialState(householdId: number) {
  const { data } = await api.get<FinancialState>(`/financial/households/${householdId}/financial-state`);
  return data;
}

export async function getCurrentFinancialPolicy(householdId: number) {
  const { data } = await api.get<FinancialPolicy>(
    `/financial/households/${householdId}/financial-policy`,
  );
  return data;
}

export async function createFinancialPolicyDecision(
  householdId: number,
  idempotencyKey: string,
) {
  const { data } = await api.post<FinancialPolicy>(
    `/financial/households/${householdId}/financial-policy/decisions`,
    undefined,
    { headers: { 'Idempotency-Key': idempotencyKey } },
  );
  return data;
}

export async function getFinancialPolicyHistory(householdId: number) {
  const { data } = await api.get<FinancialPolicyHistory>(
    `/financial/households/${householdId}/financial-policy/history`,
  );
  return data;
}

export async function getFinancialPolicyDecision(householdId: number, policyId: number) {
  const { data } = await api.get<FinancialPolicy>(
    `/financial/households/${householdId}/financial-policy/history/${policyId}`,
  );
  return data;
}

export async function getCurrentCapitalAllocation(householdId: number) {
  const { data } = await api.get<CapitalAllocation>(
    `/financial/households/${householdId}/capital-allocation`,
  );
  return data;
}

export async function getCapitalAllocationFromPolicy(householdId: number, policyId: number) {
  const { data } = await api.get<CapitalAllocation>(
    `/financial/households/${householdId}/capital-allocation/from-policy/${policyId}`,
  );
  return data;
}

export async function createCapitalAllocationDecision(
  householdId: number,
  idempotencyKey: string,
) {
  const { data } = await api.post<CapitalAllocation>(
    `/financial/households/${householdId}/capital-allocation/decisions`,
    undefined,
    { headers: { 'Idempotency-Key': idempotencyKey } },
  );
  return data;
}

export async function getCapitalAllocationHistory(householdId: number) {
  const { data } = await api.get<CapitalAllocationHistory>(
    `/financial/households/${householdId}/capital-allocation/history`,
  );
  return data;
}

export async function getCapitalAllocationDecision(householdId: number, allocationId: number) {
  const { data } = await api.get<CapitalAllocation>(
    `/financial/households/${householdId}/capital-allocation/history/${allocationId}`,
  );
  return data;
}

export async function createFinancialStateSnapshot(householdId: number, idempotencyKey: string) {
  const { data } = await api.post<FinancialStateSnapshot>(
    `/financial/households/${householdId}/financial-state/snapshots`,
    undefined,
    { headers: { 'Idempotency-Key': idempotencyKey } },
  );
  return data;
}

export async function getFinancialStateHistory(householdId: number) {
  const { data } = await api.get<FinancialStateHistory>(
    `/financial/households/${householdId}/financial-state/history`,
  );
  return data;
}

export async function listHouseholdIncomes(householdId: number) {
  const { data } = await api.get<HouseholdIncome[]>(`/financial/households/${householdId}/incomes`);
  return data;
}

export async function listHouseholdExpenses(householdId: number) {
  const { data } = await api.get<HouseholdExpense[]>(`/financial/households/${householdId}/expenses`);
  return data;
}

export async function createIncome(householdId: number, payload: IncomePayload) {
  const { data } = await api.post(`/financial/households/${householdId}/incomes`, payload);
  return data;
}

export async function createExpense(householdId: number, payload: ExpensePayload) {
  const { data } = await api.post(`/financial/households/${householdId}/expenses`, payload);
  return data;
}

export async function createLiability(householdId: number, payload: LiabilityPayload) {
  const { data } = await api.post(`/financial/households/${householdId}/debts`, payload);
  return data;
}

export async function createAsset(householdId: number, payload: AssetPayload) {
  const { data } = await api.post(`/financial/households/${householdId}/assets`, payload);
  return data;
}

export async function createGoal(householdId: number, payload: GoalPayload) {
  const { data } = await api.post(`/financial/households/${householdId}/goals`, payload);
  return data;
}
