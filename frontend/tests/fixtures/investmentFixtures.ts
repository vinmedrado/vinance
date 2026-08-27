export const authenticatedUser = {
  id: 34,
  email: 'fase34@fixture.local',
  full_name: 'Usuário Fase 34',
  is_active: true,
};

export function fakeAccessToken(expiresAt = Date.now() + 60 * 60_000) {
  const payload = Buffer.from(JSON.stringify({ sub: authenticatedUser.email, exp: Math.floor(expiresAt / 1000) })).toString('base64url');
  return `fixture.${payload}.signature`;
}

const bestRecommendation = {
  ticker: 'GARE11',
  market: 'FII',
  price: 8.23,
  quantity_possible: 36,
  invested_amount: 296.28,
  remaining_budget: 3.72,
  budget_usage_pct: 98.76,
  status: 'APPROVED',
  risk_level: 'LOW',
  recommendation_score: 87.3,
  confidence_score: 100,
  confidence_label: 'HIGH',
  explanation_quality: 'STRONG',
  trend_label: 'UPTREND',
  momentum_score: 72,
  trend_confidence: 'HIGH',
  appreciation_signal: 'HIGH',
  appreciation_text: 'Potencial quantitativo alto dentro dos sinais atuais.',
  recommendation_title: 'Ativo mais bem posicionado na análise quantitativa.',
  executive_summary: 'GARE11 lidera o ranking relativo para os filtros informados.',
  decision_summary: 'Compra quantitativamente aprovada.',
  decision_card: {
    quantity: 36,
    price: 8.23,
    invested_amount: 296.28,
    remaining_budget: 3.72,
    budget_usage_pct: 98.76,
    recommendation_score: 87.3,
    confidence_score: 100,
    appreciation_signal: 'HIGH',
  },
  score_breakdown: {
    recommendation_score: 87.3,
    fundamental_score: 84,
    profile_score: 91,
    quality_score: 86,
    liquidity_score: 88,
    risk_score: 90,
    dividend_score: 82,
    momentum_score: 72,
  },
  relative_position: { rank: 1, total_candidates: 20, percentile_label: 'TOP_5_PERCENT', text: 'Primeira posição entre vinte candidatos.' },
  why_recommended: ['Score consistente', 'Risco compatível com o perfil'],
  strengths: ['Boa liquidez', 'Fundamentos consistentes'],
  attention_points: ['Rentabilidade passada não garante retorno futuro'],
  comparison_with_alternatives: [{ ticker: 'CPTS11', reason: 'Score total inferior.' }],
};

export const completeBudgetResponse = {
  decision_id: '35000000-0000-4000-8000-000000000001',
  correlation_id: '35000000-0000-4000-8000-000000000002',
  generated_at: '2026-08-25T14:30:00Z',
  decision_action: 'BUY',
  audit_status: 'PERSISTED',
  budget: 300,
  market: 'FII',
  profile: 'CONSERVATIVE',
  best_recommendation: bestRecommendation,
  alternatives: [
    {
      ...bestRecommendation,
      ticker: 'CPTS11',
      recommendation_score: 81,
      confidence_score: 90,
      relative_position: { rank: 2, total_candidates: 20, percentile_label: 'TOP_10_PERCENT', text: 'Segunda posição.' },
    },
    {
      ...bestRecommendation,
      ticker: 'RZTR11',
      status: 'BLOCKED',
      risk_level: 'HIGH',
      recommendation_score: 92,
      confidence_score: 94,
      relative_position: { rank: 3, total_candidates: 20, percentile_label: 'TOP_25_PERCENT', text: 'Terceira posição.' },
    },
  ],
  disclaimer: 'Conteúdo educacional, sem garantia de retorno.',
};

export const emptyBudgetResponse = {
  budget: 300,
  market: 'FII',
  profile: 'CONSERVATIVE',
  best_recommendation: null,
  alternatives: [],
};

export const partialBudgetResponse = {
  budget: 300,
  market: 'FII',
  profile: 'CONSERVATIVE',
  best_recommendation: {
    ticker: 'PARC11',
    market: 'FII',
    status: 'APPROVED',
    appreciation_signal: 'UNKNOWN',
  },
  alternatives: [],
};

export const contradictoryAvoidResponse = {
  ...completeBudgetResponse,
  best_recommendation: {
    ...bestRecommendation,
    ticker: 'RISCO11',
    risk_level: 'HIGH',
    recommendation_score: 99,
    confidence_score: 99,
    recommendation_title: 'Excelente oportunidade com grande potencial.',
    executive_summary: 'O ativo apresenta sinais técnicos muito positivos.',
  },
};

export const lowScoreResponse = {
  ...completeBudgetResponse,
  best_recommendation: {
    ...bestRecommendation,
    ticker: 'BAIX11',
    status: 'REVIEW',
    recommendation_score: 42,
    confidence_score: 92,
  },
};

export const divergentConfidenceResponse = {
  ...completeBudgetResponse,
  best_recommendation: {
    ...bestRecommendation,
    ticker: 'CONF11',
    recommendation_score: 96,
    confidence_score: 20,
    confidence_label: 'HIGH',
  },
};

export const bottomRankedResponse = {
  ...completeBudgetResponse,
  best_recommendation: {
    ...bestRecommendation,
    ticker: 'BOTTOM11',
    relative_position: {
      rank: 16,
      total_candidates: 20,
      percentile_label: 'BOTTOM_50_PERCENT',
      text: 'Posição na faixa inferior dos candidatos.',
    },
  },
};

export const longContentResponse = {
  ...completeBudgetResponse,
  best_recommendation: {
    ...bestRecommendation,
    ticker: 'TICKER-EXTREMAMENTE-LONGO-SEM-ESPACOS-1234567890',
    recommendation_title: 'Explicação técnica muito longa '.repeat(18),
    executive_summary: 'Resumo executivo extenso para validar quebra de linha e ausência de overflow horizontal. '.repeat(18),
    why_recommended: ['Motivo sem espaços '.repeat(25), ...bestRecommendation.why_recommended],
  },
};

export const decisionHistoryResponse = {
  items: [
    {
      decision_id: completeBudgetResponse.decision_id,
      correlation_id: completeBudgetResponse.correlation_id,
      created_at: completeBudgetResponse.generated_at,
      asset: 'GARE11',
      market: 'FII',
      budget: '300.00',
      investor_profile: 'CONSERVATIVE',
      recommendation: 'BUY',
      quantity: 36,
      price: '8.230000',
      invested_amount: '296.28',
      remaining_amount: '3.72',
      risk_level: 'LOW',
      confidence: '100.0000',
      trend: 'UPTREND',
      ranking: 1,
      recommendation_score: '87.3000',
      guardrail_status: 'APPROVED',
      latency_ms: 41,
      fallback_used: false,
      error_code: null,
      status: 'SUCCESS',
    },
  ],
  page: 1,
  page_size: 5,
  total: 1,
  total_pages: 1,
};

export const emptyDecisionHistoryResponse = {
  items: [],
  page: 1,
  page_size: 5,
  total: 0,
  total_pages: 0,
};

export const decisionDetailResponse = {
  ...decisionHistoryResponse.items[0],
  guardrail_reasons: { blocked: [], warnings: [], summary: ['Aprovado'] },
  explanation: { executive_summary: bestRecommendation.executive_summary },
  request_parameters: { budget: '300', market: 'FII', profile: 'CONSERVATIVE', explain: true },
  input_snapshot: { selected_candidate: bestRecommendation, candidate_count: 3 },
  score_snapshot: { score_breakdown: bestRecommendation.score_breakdown },
  response_snapshot: completeBudgetResponse,
  snapshot_schema_version: 'investment-decision-audit-v1',
  rule_version: 'investment-decision-presentation-v1',
  recommendation_engine_version: 'budget-advisor-v1',
  score_version: 'vinance_score_v1',
  guardrail_version: 'vinance_guardrail_v1',
  trend_version: 'vinance_trend_v1',
};
