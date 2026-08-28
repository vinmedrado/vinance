export type RiskProfile = 'conservative' | 'moderate' | 'aggressive';

export type Income = {
  id: number; user_id: number; description: string; amount: string; income_type: string;
  received_at: string; is_recurring: boolean; created_at: string; updated_at: string;
};
export type Expense = {
  id: number; user_id: number; description: string; amount: string; category: string;
  due_date: string; paid_at?: string | null; is_paid: boolean; is_recurring: boolean; created_at: string; updated_at: string;
};
export type FinancialProfile = {
  id: number; user_id: number; monthly_salary: string; emergency_reserve: string;
  has_debt_default: boolean; risk_profile: RiskProfile; created_at: string; updated_at: string;
};
export type FinancialDiagnosis = {
  monthly_salary: string; total_expenses_30d: string; emergency_reserve: string; has_debt_default: boolean; risk_profile: RiskProfile;
  score: { score: number; level: string; penalties: string[]; recommendations: string[] };
  budget: { method: string; committed_ratio: string; total_expenses_30d: string; investment_percentage: string; investment_capacity: string; emergency_reserve_priority: boolean; high_risk_allowed: boolean; explanation: string };
};
export type IncomeCreate = { description: string; amount: number; income_type: string; received_at: string; is_recurring: boolean };
export type ExpenseCreate = { description: string; amount: number; category: string; due_date: string; paid_at?: string | null; is_paid: boolean; is_recurring: boolean };
export type FinancialProfileCreate = { monthly_salary: number; emergency_reserve: number; has_debt_default: boolean; risk_profile: RiskProfile };
