export type NumericValue = string | number;

export type TradingRiskBudget = {
  paper_only: true;
  real_trading_allowed: false;
  real_trading_capital: NumericValue;
  paper_simulation_allowed: boolean;
  financial_status: string;
  risk_budget_status: string;
  protected_capital: NumericValue | null;
  speculative_capital: NumericValue;
  blocking_reasons: string[];
  context_fingerprints: Record<string, string>;
  household_id: number;
  simulation_rules: Record<string, unknown>;
};

export type PaperAccount = {
  id: number;
  owner_user_id: number;
  ownership_scope: 'PERSONAL';
  status: string;
  quote_asset: 'USDT';
  initial_virtual_balance: NumericValue;
  cash: NumericValue;
  equity: NumericValue;
  realized_pnl: NumericValue;
  unrealized_pnl: NumericValue;
  peak_equity: NumericValue;
  max_drawdown: NumericValue;
  ruleset_version: string;
  paper_only: true;
  optimistic_version: number;
  created_at: string;
  updated_at: string;
};

export type TradingOverview = {
  paper_only: true;
  product_status: string;
  risk_budget: TradingRiskBudget;
  paper_account: PaperAccount | null;
  counts: Record<string, number>;
  performance: Record<string, NumericValue>;
  models: Record<string, unknown>;
};

export type TradingOpportunity = {
  signal_id: number;
  symbol: string;
  market: 'CRYPTO';
  interval: string;
  signal_time: string;
  freshness: string;
  side: string;
  confidence: NumericValue | null;
  score: NumericValue | null;
  reference_price: NumericValue | null;
  stop_price: NumericValue | null;
  target_price: NumericValue | null;
  model_version: string;
  feature_version: string | null;
  target_version: string | null;
  guardrail_status: string;
  reasons: string[];
};

export type PaperOrder = {
  id: number;
  paper_account_id: number;
  owner_user_id: number;
  idempotency_key: string;
  signal_id: number | null;
  symbol: string;
  market: string;
  interval: string;
  side: string;
  order_type: string;
  quantity: NumericValue;
  notional: NumericValue;
  reference_price: NumericValue;
  limit_price: NumericValue | null;
  stop_price: NumericValue | null;
  target_price: NumericValue | null;
  fee_paid: NumericValue;
  status: string;
  risk_decision: string;
  paper_only: true;
  created_at: string;
  filled_at: string | null;
};

export type PaperPosition = {
  id: number;
  paper_account_id: number;
  owner_user_id: number;
  symbol: string;
  market: string;
  interval: string;
  side: string;
  status: string;
  quantity: NumericValue;
  average_entry_price: NumericValue;
  current_reference_price: NumericValue;
  realized_pnl: NumericValue;
  unrealized_pnl: NumericValue;
  stop_price: NumericValue | null;
  target_price: NumericValue | null;
  paper_only: true;
  opened_at: string;
  closed_at: string | null;
};

export type PaperEvent = {
  id: number;
  event_type: string;
  symbol: string | null;
  event_payload: Record<string, unknown>;
  decision_context: Record<string, unknown>;
  risk_context: Record<string, unknown>;
  correlation_id: string;
  created_at: string;
};

export type TradingBacktest = {
  id: string;
  name: string;
  model: string | null;
  symbol: string | null;
  interval: string | null;
  period_start: string | null;
  period_end: string | null;
  trades: number | null;
  gross_return: NumericValue | null;
  net_return: NumericValue | null;
  win_rate: NumericValue | null;
  profit_factor: NumericValue | null;
  max_drawdown: NumericValue | null;
  sharpe: NumericValue | null;
  fees: NumericValue | null;
  slippage: NumericValue | null;
  spread: NumericValue | null;
  costs_modeled: boolean;
  status: string;
};

export type TradingModel = {
  model_id: string;
  version: string;
  symbol: string;
  interval: string;
  target_version: string;
  feature_version: string;
  artifact_checksum: string;
  created_at: string | null;
  trained_until: string | null;
  validation_status: string;
  promotion_status: string;
  metrics: Record<string, unknown>;
};

export type TradingList<T> = { items: T[]; total: number; limit: number; offset: number };

export type PaperOrderPayload = {
  idempotency_key: string;
  signal_id: number;
  symbol: string;
  market: 'CRYPTO';
  interval: string;
  side: 'BUY';
  order_type: 'MARKET';
  notional: string;
  paper_only: true;
};
