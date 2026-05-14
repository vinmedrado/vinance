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
  status: string;
}

export interface Dashboard {
  period: { year: number; month: number };
  metrics: Record<string, number>;
  budget: any;
  charts: { by_category: Array<{ name: string; value: number }>; evolution: Array<{ month: string; receitas: number; despesas: number }> };
  recommendation: { title: string; message: string; amount: number };
  alerts: Array<{ severity: string; title: string; message: string }>;
}

export interface Diagnosis {
  score: number;
  status: string;
  alerts: Array<{ severity: string; title: string; message: string }>;
  recommendations: Array<{ title: string; message: string; amount?: number }>;
  forecast: { expected_close: number; confidence: string; message: string };
  investment_connection: { recommended_monthly_amount: number; available_now: number; difference_vs_plan: number; message: string };
}
