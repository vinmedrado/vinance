import { api } from '../../../services/api';
import type {
  ActionPlan,
  ActionPlanHistory,
  AssetPayload,
  CapitalAllocation,
  CapitalAllocationHistory,
  ContinuousAutopilot,
  ContinuousAutopilotHistory,
  ExpensePayload,
  FinancialState,
  FinancialStateHistory,
  FinancialPolicy,
  FinancialPolicyHistory,
  FinancialStateSnapshot,
  GoalPayload,
  Household,
  HouseholdExpense,
  HouseholdGoal,
  HouseholdIncome,
  HouseholdLiability,
  HouseholdOwnedAsset,
  IncomePayload,
  InvestmentOrchestration,
  InvestmentOrchestrationHistory,
  LiabilityPayload,
  IncomeUpdatePayload,
  ExpenseUpdatePayload,
  LiabilityUpdatePayload,
  AssetUpdatePayload,
  GoalUpdatePayload,
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

export async function getCurrentInvestmentOrchestration(householdId: number) {
  const { data } = await api.get<InvestmentOrchestration>(
    `/financial/households/${householdId}/investment-orchestration`,
  );
  return data;
}

export async function getInvestmentOrchestrationFromAllocation(
  householdId: number,
  allocationId: number,
) {
  const { data } = await api.get<InvestmentOrchestration>(
    `/financial/households/${householdId}/investment-orchestration/from-allocation/${allocationId}`,
  );
  return data;
}

export async function createInvestmentOrchestrationDecision(
  householdId: number,
  idempotencyKey: string,
) {
  const { data } = await api.post<InvestmentOrchestration>(
    `/financial/households/${householdId}/investment-orchestration/decisions`,
    undefined,
    { headers: { 'Idempotency-Key': idempotencyKey } },
  );
  return data;
}

export async function getInvestmentOrchestrationHistory(householdId: number) {
  const { data } = await api.get<InvestmentOrchestrationHistory>(
    `/financial/households/${householdId}/investment-orchestration/history`,
  );
  return data;
}

export async function getInvestmentOrchestrationDecision(
  householdId: number,
  orchestrationId: number,
) {
  const { data } = await api.get<InvestmentOrchestration>(
    `/financial/households/${householdId}/investment-orchestration/history/${orchestrationId}`,
  );
  return data;
}

export async function getCurrentActionPlan(householdId: number) {
  const { data } = await api.get<ActionPlan>(
    `/financial/households/${householdId}/action-plan`,
  );
  return data;
}

export async function getActionPlanFromOrchestration(
  householdId: number,
  orchestrationId: number,
) {
  const { data } = await api.get<ActionPlan>(
    `/financial/households/${householdId}/action-plan/from-orchestration/${orchestrationId}`,
  );
  return data;
}

export async function createActionPlanDecision(
  householdId: number,
  idempotencyKey: string,
) {
  const { data } = await api.post<ActionPlan>(
    `/financial/households/${householdId}/action-plan/decisions`,
    undefined,
    { headers: { 'Idempotency-Key': idempotencyKey } },
  );
  return data;
}

export async function getActionPlanHistory(householdId: number) {
  const { data } = await api.get<ActionPlanHistory>(
    `/financial/households/${householdId}/action-plan/history`,
  );
  return data;
}

export async function getActionPlanDecision(
  householdId: number,
  actionPlanId: number,
) {
  const { data } = await api.get<ActionPlan>(
    `/financial/households/${householdId}/action-plan/history/${actionPlanId}`,
  );
  return data;
}

export async function getCurrentContinuousAutopilot(householdId: number) {
  const { data } = await api.get<ContinuousAutopilot>(
    `/financial/households/${householdId}/continuous-autopilot`,
  );
  return data;
}

export async function evaluateContinuousAutopilot(
  householdId: number,
  idempotencyKey: string,
) {
  const { data } = await api.post<ContinuousAutopilot>(
    `/financial/households/${householdId}/continuous-autopilot/evaluate`,
    {},
    { headers: { 'Idempotency-Key': idempotencyKey } },
  );
  return data;
}

export async function getContinuousAutopilotHistory(householdId: number) {
  const { data } = await api.get<ContinuousAutopilotHistory>(
    `/financial/households/${householdId}/continuous-autopilot/history`,
  );
  return data;
}

export async function getContinuousAutopilotDecision(
  householdId: number,
  decisionId: number,
) {
  const { data } = await api.get<ContinuousAutopilot>(
    `/financial/households/${householdId}/continuous-autopilot/history/${decisionId}`,
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

export async function listHouseholdIncomes(householdId: number, signal?: AbortSignal) {
  const { data } = await api.get<HouseholdIncome[]>(`/financial/households/${householdId}/incomes`, { signal });
  return data;
}

export async function listHouseholdExpenses(householdId: number, signal?: AbortSignal) {
  const { data } = await api.get<HouseholdExpense[]>(`/financial/households/${householdId}/expenses`, { signal });
  return data;
}

export async function listHouseholdLiabilities(householdId: number, signal?: AbortSignal) {
  const { data } = await api.get<HouseholdLiability[]>(`/financial/households/${householdId}/debts`, { signal });
  return data;
}

export async function listHouseholdAssets(householdId: number, signal?: AbortSignal) {
  const { data } = await api.get<HouseholdOwnedAsset[]>(`/financial/households/${householdId}/assets`, { signal });
  return data;
}

export async function listHouseholdGoals(householdId: number, signal?: AbortSignal) {
  const { data } = await api.get<HouseholdGoal[]>(`/financial/households/${householdId}/goals`, { signal });
  return data;
}

export async function createIncome(householdId: number, payload: IncomePayload) {
  const { data } = await api.post<HouseholdIncome>(`/financial/households/${householdId}/incomes`, payload);
  return data;
}

export async function createExpense(householdId: number, payload: ExpensePayload) {
  const { data } = await api.post<HouseholdExpense>(`/financial/households/${householdId}/expenses`, payload);
  return data;
}

export async function createLiability(householdId: number, payload: LiabilityPayload) {
  const { data } = await api.post<HouseholdLiability>(`/financial/households/${householdId}/debts`, payload);
  return data;
}

export async function createAsset(householdId: number, payload: AssetPayload) {
  const { data } = await api.post<HouseholdOwnedAsset>(`/financial/households/${householdId}/assets`, payload);
  return data;
}

export async function createGoal(householdId: number, payload: GoalPayload) {
  const { data } = await api.post<HouseholdGoal>(`/financial/households/${householdId}/goals`, payload);
  return data;
}

export async function updateIncome(householdId: number, recordId: number, payload: IncomeUpdatePayload) {
  const { data } = await api.patch<HouseholdIncome>(`/financial/households/${householdId}/incomes/${recordId}`, payload);
  return data;
}

export async function updateExpense(householdId: number, recordId: number, payload: ExpenseUpdatePayload) {
  const { data } = await api.patch<HouseholdExpense>(`/financial/households/${householdId}/expenses/${recordId}`, payload);
  return data;
}

export async function updateLiability(householdId: number, recordId: number, payload: LiabilityUpdatePayload) {
  const { data } = await api.patch<HouseholdLiability>(`/financial/households/${householdId}/debts/${recordId}`, payload);
  return data;
}

export async function updateAsset(householdId: number, recordId: number, payload: AssetUpdatePayload) {
  const { data } = await api.patch<HouseholdOwnedAsset>(`/financial/households/${householdId}/assets/${recordId}`, payload);
  return data;
}

export async function updateGoal(householdId: number, recordId: number, payload: GoalUpdatePayload) {
  const { data } = await api.patch<HouseholdGoal>(`/financial/households/${householdId}/goals/${recordId}`, payload);
  return data;
}

export async function deleteIncome(householdId: number, recordId: number) {
  await api.delete(`/financial/households/${householdId}/incomes/${recordId}`);
}

export async function deleteExpense(householdId: number, recordId: number) {
  await api.delete(`/financial/households/${householdId}/expenses/${recordId}`);
}

export async function deleteLiability(householdId: number, recordId: number) {
  await api.delete(`/financial/households/${householdId}/debts/${recordId}`);
}

export async function deleteAsset(householdId: number, recordId: number) {
  await api.delete(`/financial/households/${householdId}/assets/${recordId}`);
}

export async function deleteGoal(householdId: number, recordId: number) {
  await api.delete(`/financial/households/${householdId}/goals/${recordId}`);
}
