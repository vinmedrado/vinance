export type InvestorProfile = 'CONSERVATIVE' | 'MODERATE' | 'AGGRESSIVE';
export type RiskLevel = 'LOW' | 'MEDIUM' | 'HIGH' | 'UNKNOWN' | string;
export type TrendLabel = 'UPTREND' | 'SIDEWAYS' | 'DOWNTREND' | 'INSUFFICIENT_HISTORY' | string;
export type AppreciationSignal = 'LOW' | 'MODERATE' | 'HIGH' | 'UNKNOWN' | string;

export type DecisionCard = {
  ticker?: string;
  action?: string;
  quantity?: number | string;
  price?: number | string;
  invested_amount?: number | string;
  remaining_budget?: number | string;
  budget_usage_pct?: number | string;
  recommendation_score?: number | string;
  confidence_score?: number | string;
  appreciation_signal?: AppreciationSignal;
};

export type ScoreBreakdown = {
  recommendation_score?: number | string;
  fundamental_score?: number | string;
  profile_score?: number | string;
  quality_score?: number | string;
  liquidity_score?: number | string;
  risk_score?: number | string;
  dividend_score?: number | string;
  momentum_score?: number | string;
};

export type RelativePosition = {
  rank?: number;
  total_candidates?: number;
  percentile_label?: string;
  text?: string;
};

export type AlternativeComparison = {
  ticker?: string;
  reason?: string;
};

export type RecommendationExplanation = {
  recommendation_title?: string;
  decision_summary?: string;
  executive_summary?: string;
  decision_card?: DecisionCard;
  score_breakdown?: ScoreBreakdown;
  relative_position?: RelativePosition;
  strengths?: string[];
  attention_points?: string[];
  comparison_with_alternatives?: AlternativeComparison[];
  why_recommended?: string[];
  appreciation_signal?: AppreciationSignal;
  appreciation_text?: string;
  confidence_score?: number | string;
  confidence_label?: string;
  budget_usage_pct?: number | string;
  remaining_budget?: number | string;
  explanation_quality?: string;
  disclaimer?: string;
};

export type BudgetRecommendation = RecommendationExplanation & {
  ticker: string;
  market: string;
  date?: string;
  price?: number | string;
  quantity_possible?: number | string;
  invested_amount?: number | string;
  score_total?: number | string;
  score_quality?: number | string;
  score_liquidity?: number | string;
  score_risk?: number | string;
  score_dividend?: number | string;
  profile?: InvestorProfile | string;
  profile_score?: number | string;
  recommendation_score?: number | string;
  status?: string;
  risk_level?: RiskLevel;
  trend_label?: TrendLabel | null;
  momentum_score?: number | string;
  trend_confidence?: string | null;
  trend_method?: string | null;
  recommendation_components_json?: Record<string, unknown> | null;
  reasons_json?: string[] | Record<string, unknown> | null;
};

export type ExplainedBudgetAdvisorResponse = {
  decision_id?: string;
  correlation_id?: string;
  generated_at?: string;
  decision_action?: DecisionAuditAction;
  audit_status?: 'PERSISTED' | 'FAILED' | string;
  budget: number | string;
  market: string;
  profile: InvestorProfile | string;
  best_recommendation?: BudgetRecommendation | null;
  alternatives?: BudgetRecommendation[];
  disclaimer?: string;
  integration_warnings?: string[];
};

export type DecisionAuditAction = 'BUY' | 'WAIT' | 'AVOID' | 'NO_RECOMMENDATION' | string;
export type DecisionAuditStatus = 'SUCCESS' | 'EMPTY' | 'ERROR' | string;

export type InvestmentDecisionHistoryItem = {
  decision_id: string;
  correlation_id: string;
  created_at: string;
  asset?: string | null;
  market?: string | null;
  budget: number | string;
  investor_profile?: string | null;
  recommendation: DecisionAuditAction;
  quantity?: number | null;
  price?: number | string | null;
  invested_amount?: number | string | null;
  remaining_amount?: number | string | null;
  risk_level?: RiskLevel | null;
  confidence?: number | string | null;
  trend?: TrendLabel | null;
  ranking?: number | null;
  recommendation_score?: number | string | null;
  guardrail_status?: string | null;
  latency_ms: number;
  fallback_used: boolean;
  error_code?: string | null;
  status: DecisionAuditStatus;
};

export type InvestmentDecisionHistoryPage = {
  items: InvestmentDecisionHistoryItem[];
  page: number;
  page_size: number;
  total: number;
  total_pages: number;
};

export type InvestmentDecisionDetail = InvestmentDecisionHistoryItem & {
  guardrail_reasons: Record<string, unknown>;
  explanation: Record<string, unknown>;
  request_parameters: Record<string, unknown>;
  input_snapshot: Record<string, unknown>;
  score_snapshot: Record<string, unknown>;
  response_snapshot: Record<string, unknown>;
  snapshot_schema_version: string;
  rule_version: string;
  recommendation_engine_version: string;
  score_version?: string | null;
  guardrail_version?: string | null;
  trend_version?: string | null;
};

export type InvestmentWorkspaceFilters = {
  budget: number;
  market: string;
  profile: InvestorProfile;
  includeWarnings: boolean;
};

export type PerformanceHorizon = '1d' | '7d' | '30d';
export type PerformanceClassification =
  | 'STRONGLY_CORRECT'
  | 'CORRECT'
  | 'NEUTRAL'
  | 'INCORRECT'
  | 'STRONGLY_INCORRECT';

export type PerformanceMetricGroup = {
  key: string;
  total: number;
  total_eligible: number;
  evaluated: number;
  pending: number;
  average_return_pct?: number | null;
  median_return_pct?: number | null;
  positive_pct?: number | null;
  negative_pct?: number | null;
  directional_accuracy_pct?: number | null;
  directional_sample: number;
  neutral: number;
  period?: string;
  horizon?: PerformanceHorizon;
  mean_confidence?: number | null;
  calibration_gap_pct?: number | null;
  diagnostic?: string;
};

export type InvestmentPerformanceSummary = {
  as_of: string;
  selected_horizon?: PerformanceHorizon | null;
  total_decisions: number;
  eligible_decisions: number;
  evaluated: number;
  pending: number;
  average_return_pct?: number | null;
  median_return_pct?: number | null;
  positive_pct?: number | null;
  negative_pct?: number | null;
  directional_accuracy_pct?: number | null;
  directional_sample: number;
  by_horizon: PerformanceMetricGroup[];
  by_action: PerformanceMetricGroup[];
  by_asset: PerformanceMetricGroup[];
  by_risk: PerformanceMetricGroup[];
  by_confidence: PerformanceMetricGroup[];
  by_score_band: PerformanceMetricGroup[];
  by_profile: PerformanceMetricGroup[];
  by_rule_version: PerformanceMetricGroup[];
  by_recommendation_engine_version: PerformanceMetricGroup[];
  by_score_version: PerformanceMetricGroup[];
  by_guardrail_version: PerformanceMetricGroup[];
  by_version_cohort: PerformanceMetricGroup[];
  mixed_versions: boolean;
  calibration: PerformanceMetricGroup[];
  calibration_summary: Record<string, unknown>;
  timeline: PerformanceMetricGroup[];
};

export type InvestmentPerformanceEvaluation = {
  horizon: PerformanceHorizon;
  reference_price: number | string;
  reference_price_timestamp: string;
  price_source: string;
  evaluation_price: number | string;
  evaluation_timestamp: string;
  evaluation_price_source: string;
  absolute_change: number | string;
  return_pct: number | string;
  max_favorable_excursion_pct?: number | string | null;
  max_adverse_excursion_pct?: number | string | null;
  result_status: 'EVALUATED';
  result_classification: PerformanceClassification;
  result_context: Record<string, unknown>;
  evaluation_policy_version: string;
  evaluated_at: string;
};

export type InvestmentDecisionPerformanceDetail = {
  decision_id: string;
  asset: string;
  action: 'BUY' | 'WAIT' | 'AVOID';
  decision_created_at: string;
  risk_level?: string | null;
  confidence?: number | string | null;
  trend?: string | null;
  recommendation_score?: number | string | null;
  investor_profile?: string | null;
  rule_version: string;
  recommendation_engine_version: string;
  score_version?: string | null;
  guardrail_version?: string | null;
  reference_price?: number | string | null;
  reference_price_timestamp?: string | null;
  price_source?: string | null;
  evaluations: InvestmentPerformanceEvaluation[];
  pending_horizons: PerformanceHorizon[];
  eligible_pending_horizons: PerformanceHorizon[];
  immature_horizons: PerformanceHorizon[];
};

export type InvestmentAlertType =
  | 'NEW_OPPORTUNITY'
  | 'ACTION_CHANGE'
  | 'SCORE_CHANGE'
  | 'CONFIDENCE_CHANGE'
  | 'RISK_CHANGE';

export type InvestmentAlertSeverity = 'INFO' | 'MEDIUM' | 'HIGH';

export type InvestmentAlertSubscription = {
  id: number;
  asset: string;
  market: string;
  budget: number;
  investor_profile: string;
  source_decision_id: string;
  enabled: boolean;
  alert_on_action_change: boolean;
  alert_on_score_change: boolean;
  alert_on_confidence_change: boolean;
  alert_on_risk_change: boolean;
  alert_on_new_opportunity: boolean;
  minimum_score_delta: number;
  minimum_confidence_delta: number;
  cooldown_minutes: number;
  rule_version: string;
  created_at: string;
  updated_at: string;
};

export type InvestmentAlertSubscriptionList = {
  items: InvestmentAlertSubscription[];
  total: number;
  active: number;
  limit: number;
};

export type InvestmentAlertSubscriptionCreate = {
  asset: string;
  source_decision_id: string;
};

export type InvestmentAlertSubscriptionUpdate = Partial<Pick<
  InvestmentAlertSubscription,
  | 'enabled'
  | 'alert_on_action_change'
  | 'alert_on_score_change'
  | 'alert_on_confidence_change'
  | 'alert_on_risk_change'
  | 'alert_on_new_opportunity'
  | 'minimum_score_delta'
  | 'minimum_confidence_delta'
  | 'cooldown_minutes'
>>;

export type InvestmentAlertState = Record<string, unknown> & {
  decision_id?: string | null;
  action?: DecisionAuditAction | null;
  score?: number | string | null;
  recommendation_score?: number | string | null;
  confidence?: number | string | null;
  risk_level?: RiskLevel | null;
  trend?: TrendLabel | null;
};

export type InvestmentAlertItem = {
  alert_id: string;
  subscription_id?: number | null;
  decision_id: string;
  asset: string;
  alert_type: InvestmentAlertType;
  severity: InvestmentAlertSeverity;
  delivery_channel: 'IN_APP';
  message: string;
  created_at: string;
  read_at?: string | null;
};

export type InvestmentAlertDetail = InvestmentAlertItem & {
  previous_state: InvestmentAlertState;
  current_state: InvestmentAlertState;
  rule_version: string;
};

export type InvestmentAlertsPage = {
  items: InvestmentAlertItem[];
  page: number;
  page_size: number;
  total: number;
  total_pages: number;
  unread_count: number;
};

export type InvestmentAlertsFilters = {
  page?: number;
  pageSize?: number;
  asset?: string;
  alertType?: InvestmentAlertType | '';
  severity?: InvestmentAlertSeverity | '';
  unreadOnly?: boolean;
  dateFrom?: string;
  dateTo?: string;
};
