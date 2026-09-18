export type OwnershipScope = 'PERSONAL' | 'HOUSEHOLD';
export type DataQuality = 'COMPLETE' | 'PARTIAL' | 'INSUFFICIENT' | 'STALE' | 'INCONSISTENT';
export type MoneyValue = string | number | null;

export type Household = {
  id: number;
  name: string;
  household_type: 'PERSONAL' | 'SHARED';
  created_by_user_id: number;
  status: 'ACTIVE' | 'ARCHIVED';
  created_at: string;
  updated_at: string;
};

export type HouseholdIncome = {
  id: number;
  household_id: number;
  user_id: number;
  ownership_scope: OwnershipScope;
  description: string;
  amount: MoneyValue;
  income_type: string;
  received_at: string;
  is_recurring: boolean;
  created_at: string;
  updated_at: string;
};

export type HouseholdExpense = {
  id: number;
  household_id: number;
  user_id: number;
  ownership_scope: OwnershipScope;
  description: string;
  amount: MoneyValue;
  category: string;
  due_date: string;
  paid_at: string | null;
  is_paid: boolean;
  is_recurring: boolean;
  expense_nature: 'FIXED' | 'VARIABLE' | null;
  created_at: string;
  updated_at: string;
};

export type AssetDistribution = Record<string, {
  amount: MoneyValue;
  percentage: MoneyValue;
}>;

export type FinancialStateMetrics = {
  recurring_monthly_income: MoneyValue;
  non_recurring_income: MoneyValue;
  total_income: MoneyValue;
  fixed_expenses: MoneyValue;
  variable_expenses: MoneyValue;
  total_expenses: MoneyValue;
  cash_flow: MoneyValue;
  disposable_income: MoneyValue;
  savings_capacity: MoneyValue;
  investment_capacity: MoneyValue;
  total_assets: MoneyValue;
  total_liabilities: MoneyValue;
  net_worth: MoneyValue;
  emergency_reserve: MoneyValue;
  emergency_reserve_months: MoneyValue;
  monthly_debt_service: MoneyValue;
  debt_to_income: MoneyValue;
  debt_service_ratio: MoneyValue;
  savings_rate: MoneyValue;
  asset_distribution: AssetDistribution | null;
};

export type FinancialStateGoal = {
  id: number;
  user_id: number;
  ownership_scope: OwnershipScope;
  name: string;
  target_amount: MoneyValue;
  current_amount: MoneyValue;
  funding_gap: MoneyValue;
  deadline: string | null;
  priority: 'LOW' | 'MEDIUM' | 'HIGH';
  status: string;
};

export type MemberFinancialView = {
  user_id: number;
  full_name: string | null;
  metrics: FinancialStateMetrics;
  goals: FinancialStateGoal[];
  missing_fields: string[];
  inconsistencies: string[];
  provenance: Record<string, unknown>;
};

export type FinancialState = {
  household_id: number;
  engine_version: string;
  evaluated_at: string;
  metrics: FinancialStateMetrics;
  goals: FinancialStateGoal[];
  member_views: MemberFinancialView[];
  data_quality: DataQuality;
  confidence: number;
  missing_fields: string[];
  inconsistencies: string[];
  stale_fields: string[];
  provenance: Record<string, unknown>;
};

export type FinancialStateSnapshot = {
  id: number;
  household_id: number;
  created_by_user_id: number;
  evaluated_at: string;
  engine_version: string;
  normalized_inputs: Record<string, unknown>;
  metrics: FinancialStateMetrics;
  member_views: MemberFinancialView[];
  data_quality: DataQuality;
  confidence: number;
  missing_fields: string[];
  inconsistencies: string[];
  input_fingerprint: string;
  idempotency_key: string | null;
  created_at: string;
};

export type FinancialStateHistory = {
  items: FinancialStateSnapshot[];
  total: number;
};

export type FinancialPolicyState =
  | 'DATA_BLOCKED'
  | 'CASHFLOW_RECOVERY'
  | 'DEBT_PRIORITY'
  | 'EMERGENCY_RESERVE_PRIORITY'
  | 'GOAL_PRIORITY'
  | 'BALANCED_BUILD'
  | 'INVESTMENT_READY';

export type InvestmentReadiness = 'BLOCKED' | 'LIMITED' | 'READY';

export type FinancialPolicyMessage = {
  code: string;
  message: string;
  fields: string[];
  rule_ids: string[];
};

export type FinancialPriority = {
  rank: number;
  code: string;
  title: string;
  explanation: string;
  status: 'ACTIVE' | 'NEXT' | 'CONDITIONAL' | 'BLOCKED';
  evidence_refs: string[];
};

export type FinancialPolicyEvidence = {
  code: string;
  label: string;
  value: unknown;
  unit: string;
  source: string;
};

export type FinancialPolicyExplanation = {
  code: string;
  decision: string;
  reason: string;
  evidence_refs: string[];
  rule_ids: string[];
  blocked_alternatives: string[];
};

export type MemberPolicyView = {
  user_id: number;
  full_name: string | null;
  scope: 'PERSONAL_ONLY';
  policy_state: FinancialPolicyState;
  investment_readiness: InvestmentReadiness;
  priority_signals: string[];
  metrics: FinancialStateMetrics;
  goals: FinancialStateGoal[];
  missing_information: string[];
  inconsistencies: string[];
  explanation: string;
};

export type FinancialPolicy = {
  policy_id: number | null;
  household_id: number;
  financial_state_snapshot_id: number | null;
  engine_version: 'financial-policy-v1';
  rules_version: string;
  evaluated_at: string;
  generated_at: string;
  created_at: string | null;
  input_fingerprint: string;
  ruleset_fingerprint: string;
  decision_fingerprint: string;
  policy_state: FinancialPolicyState;
  investment_readiness: InvestmentReadiness;
  summary: string;
  priority_stack: FinancialPriority[];
  data_gate: {
    status: 'BLOCKED' | 'LIMITED' | 'PASS';
    critical_missing_fields: string[];
    readiness_missing_fields: string[];
    critical_stale_fields: string[];
    currencies: string[];
    missing_currency_fields: string[];
    readiness_limiters: string[];
  };
  debt_policy: Record<string, unknown>;
  reserve_policy: Record<string, unknown>;
  goal_policy: Record<string, unknown>;
  blockers: FinancialPolicyMessage[];
  warnings: FinancialPolicyMessage[];
  limitations: FinancialPolicyMessage[];
  missing_information: FinancialPolicyMessage[];
  explanations: FinancialPolicyExplanation[];
  evidence: FinancialPolicyEvidence[];
  member_policy_views: MemberPolicyView[];
  rules_evaluated: Array<Record<string, unknown>>;
  ruleset: Record<string, unknown>;
  source_financial_state: Record<string, unknown>;
  previous_financial_state: Record<string, unknown>;
};

export type FinancialPolicyDecisionSummary = {
  policy_id: number;
  household_id: number;
  financial_state_snapshot_id: number;
  engine_version: string;
  rules_version: string;
  policy_state: FinancialPolicyState;
  investment_readiness: InvestmentReadiness;
  decision_fingerprint: string;
  generated_at: string;
  created_at: string;
};

export type FinancialPolicyHistory = {
  items: FinancialPolicyDecisionSummary[];
  total: number;
};

export type CapitalAllocationStatus = 'BLOCKED' | 'CONSTRAINED' | 'ACTIVE' | 'SURPLUS';
export type CapitalAllocationBucket =
  | 'INFORMATIONAL'
  | 'PROTECTED_CAPITAL'
  | 'GOAL_CAPITAL'
  | 'INVESTMENT_CAPITAL'
  | 'SPECULATIVE_CAPITAL';

export type CapitalAllocationMessage = {
  code: string;
  message: string;
  fields: string[];
  rule_ids: string[];
};

export type CapitalAllocationEvidence = {
  code: string;
  label: string;
  value: unknown;
  unit: string;
  source: string;
};

export type CapitalAllocationItem = {
  priority_code: string;
  priority_rank: number;
  bucket_type: CapitalAllocationBucket;
  target_type: 'DATA' | 'CASH_FLOW' | 'LIABILITY' | 'EMERGENCY_RESERVE' | 'GOAL' | 'INVESTMENT';
  target_id: number | string | null;
  target_name: string | null;
  ownership_scope: OwnershipScope | null;
  user_id: number | string | null;
  requested_amount: MoneyValue;
  allocated_amount: string | number;
  remaining_need: MoneyValue;
  status: 'NOT_CALCULABLE' | 'UNFUNDED' | 'PARTIALLY_FUNDED' | 'FUNDED' | 'ALLOCATED' | 'BLOCKED';
  reason: string;
  evidence_refs: string[];
};

export type CapitalAllocationMemberImpact = {
  user_id: number;
  full_name: string | null;
  personal_allocatable_capital: MoneyValue;
  allocated_to_personal_priorities: string | number;
  remaining_personal_capacity: MoneyValue;
  explanation: string;
};

export type CapitalAllocation = {
  allocation_id: number | null;
  household_id: number;
  financial_state_snapshot_id: number | null;
  financial_policy_id: number | null;
  engine_version: 'capital-allocation-v1';
  rules_version: 'capital-allocation-rules-v1';
  allocation_period: 'MONTHLY';
  allocation_status: CapitalAllocationStatus;
  currency: string;
  allocatable_capital: MoneyValue;
  allocated_capital: string | number;
  remaining_capital: MoneyValue;
  investment_bucket_amount: string | number;
  bucket_totals: {
    protected_capital: string | number;
    goal_capital: string | number;
    investment_capital: string | number;
    speculative_capital: string | number;
  };
  allocations: CapitalAllocationItem[];
  unfunded_priorities: CapitalAllocationItem[];
  member_impacts: CapitalAllocationMemberImpact[];
  blockers: CapitalAllocationMessage[];
  warnings: CapitalAllocationMessage[];
  missing_information: CapitalAllocationMessage[];
  evidence: CapitalAllocationEvidence[];
  rules_evaluated: Array<Record<string, unknown>>;
  data_gate: {
    status: 'BLOCKED' | 'LIMITED' | 'PASS';
    state_quality: DataQuality | string;
    state_confidence: number | null;
    policy_state: FinancialPolicyState | null;
    investment_readiness: InvestmentReadiness | null;
    currencies: string[];
    critical_stale_fields: string[];
    consistency_checks: Record<string, boolean>;
  };
  ruleset: Record<string, unknown>;
  source_financial_state: Record<string, unknown>;
  source_financial_policy: Record<string, unknown>;
  input_fingerprint: string;
  policy_fingerprint: string;
  ruleset_fingerprint: string;
  decision_fingerprint: string;
  generated_at: string;
  created_at: string | null;
};

export type CapitalAllocationDecisionSummary = {
  allocation_id: number;
  household_id: number;
  financial_state_snapshot_id: number;
  financial_policy_id: number;
  engine_version: string;
  rules_version: string;
  allocation_period: 'MONTHLY';
  allocation_status: CapitalAllocationStatus;
  currency: string;
  allocatable_capital: MoneyValue;
  allocated_capital: string | number;
  investment_bucket_amount: string | number;
  decision_fingerprint: string;
  generated_at: string;
  created_at: string;
};

export type CapitalAllocationHistory = {
  items: CapitalAllocationDecisionSummary[];
  total: number;
};

export type IncomePayload = {
  ownership_scope: OwnershipScope;
  description: string;
  amount: number;
  income_type: string;
  received_at: string;
  is_recurring: boolean;
};

export type ExpensePayload = {
  ownership_scope: OwnershipScope;
  description: string;
  amount: number;
  category: string;
  due_date: string;
  paid_at?: string | null;
  is_paid: boolean;
  is_recurring: boolean;
  expense_nature: 'FIXED' | 'VARIABLE';
};

export type LiabilityPayload = {
  ownership_scope: OwnershipScope;
  name: string;
  liability_type: string;
  current_balance?: number | null;
  monthly_payment?: number | null;
  annual_interest_rate_pct?: number | null;
  due_date?: string | null;
  balance_as_of?: string | null;
  currency?: string;
};

export type AssetPayload = {
  ownership_scope: OwnershipScope;
  asset_class: 'CASH' | 'EMERGENCY_RESERVE' | 'FIXED_INCOME' | 'INVESTMENTS' | 'REAL_ESTATE' | 'VEHICLES' | 'OTHER';
  asset_catalog_id?: number | null;
  name?: string | null;
  current_value?: number | null;
  value_as_of?: string | null;
  currency?: string;
};

export type GoalPayload = {
  ownership_scope: OwnershipScope;
  name: string;
  target_amount: number;
  current_amount?: number | null;
  deadline?: string | null;
  priority: 'LOW' | 'MEDIUM' | 'HIGH';
};
