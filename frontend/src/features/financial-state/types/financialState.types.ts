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
