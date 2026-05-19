export type Status = 'paid' | 'pending' | 'overdue' | 'received';

export interface Expense {
  id: number;
  amount: number;
  description: string;
  category?: string | null;
  subcategory?: string | null;
  due_date: string;
  paid_at?: string | null;
  recurrence: string;
  payment_method?: string | null;
  account_id?: number | null;
  card_id?: number | null;
  status: Status | string;
  tags?: string | null;
  notes?: string | null;
}

export interface Income {
  id: number;
  amount: number;
  description: string;
  received_at: string;
  recurrence?: string | null;
  status: string;
  notes?: string | null;
}

export interface IntelligentMarketRecommendation {
  name: string;
  market: string;
  allocation_pct: number;
  amount: number;
  risk: string;
  reason: string;
}

export interface IntelligentAllocation {
  can_invest: boolean;
  decision: string;
  next_action: string;
  method: { id: string; name: string; needs_pct: number; wants_pct: number; investments_pct: number; reason: string };
  risk_profile: string;
  income: number;
  expenses: number;
  balance: number;
  expense_ratio_pct: number;
  investable_amount: number;
  emergency_reserve_target: number;
  emergency_reserve_gap: number;
  groups: { needs: number; wants: number; investment: number };
  markets: IntelligentMarketRecommendation[];
  advisor_notes: string[];
}

export interface Dashboard {
  period: { year: number; month: number };
  metrics: Record<string, number>;
  budget: any;
  charts: { by_category: Array<{ name: string; value: number }>; evolution: Array<{ month: string; receitas: number; despesas: number }> };
  recommendation: { title: string; message: string; amount: number };
  alerts: Array<{ severity: string; title: string; message: string }>;
  intelligent_allocation?: IntelligentAllocation;
}

export interface Diagnosis {
  score: number;
  status: string;
  alerts: Array<{ severity: string; title: string; message: string }>;
  recommendations: Array<{ title: string; message: string; amount?: number }>;
  forecast: { expected_close: number; confidence: string; message: string };
  investment_connection: { recommended_monthly_amount: number; available_now: number; difference_vs_plan: number; message: string };
}
