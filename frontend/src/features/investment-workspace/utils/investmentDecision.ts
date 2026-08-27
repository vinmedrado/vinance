import type { BudgetRecommendation } from '../types/investmentWorkspace.types';
import { formatCurrency, formatPercent } from '../../../utils/formatters';

export type VisualTone = 'success' | 'warning' | 'danger' | 'neutral';

export type SuggestedAction = {
  label: 'Comprar' | 'Aguardar' | 'Evitar';
  tone: Exclude<VisualTone, 'neutral'>;
  reason: string;
};

export type OpportunityRating = {
  stars: number;
  label: string;
  compositeScore: number | null;
  tone: VisualTone;
};

export type DecisionPresentation = {
  action: SuggestedAction;
  rating: OpportunityRating;
  tone: VisualTone;
  eyebrow: string;
  headline: string;
};

export function numberValue(value?: unknown) {
  if (value === null || value === undefined || value === '') return null;
  const result = Number(value);
  return Number.isFinite(result) ? result : null;
}

function normalized(value?: unknown) {
  const result = numberValue(value);
  if (result === null) return null;
  return Number.isFinite(result) ? Math.max(0, Math.min(100, result)) : null;
}

export function scoreValue(value?: unknown) {
  return normalized(value);
}

export function currencyText(value?: unknown) {
  const number = numberValue(value);
  return number === null ? '—' : formatCurrency(number);
}

export function percentText(value?: unknown) {
  const number = numberValue(value);
  return number === null ? '—' : formatPercent(number);
}

export function scoreText(value?: unknown) {
  const number = numberValue(value);
  return number === null ? '—' : number.toFixed(1).replace('.', ',');
}

export function quantityText(value?: unknown) {
  const number = numberValue(value);
  return number === null ? '—' : Math.max(0, Math.trunc(number)).toLocaleString('pt-BR');
}

export function quantitativeChance(score?: unknown) {
  const value = scoreValue(score);
  if (value === null) return 'Indefinida';
  if (value >= 95) return 'Excelente';
  if (value >= 90) return 'Muito alta';
  if (value >= 80) return 'Alta';
  if (value >= 70) return 'Boa';
  if (value >= 60) return 'Moderada';
  return 'Baixa';
}

function normalizedLabel(label?: unknown, fallback = '') {
  return typeof label === 'string' ? label.toUpperCase() : fallback;
}

export function scoreTone(value?: unknown): VisualTone {
  const score = normalized(value);
  if (score === null) return 'neutral';
  if (score >= 75) return 'success';
  if (score >= 60) return 'warning';
  return 'danger';
}

export function confidenceLabel(label?: unknown) {
  return ({ HIGH: 'Alta', MEDIUM: 'Média', LOW: 'Baixa' } as Record<string, string>)[normalizedLabel(label)] ?? 'Indefinida';
}

export function confidenceCodeFromScore(score?: unknown) {
  const value = normalized(score);
  if (value === null) return null;
  if (value >= 80) return 'HIGH';
  if (value >= 60) return 'MEDIUM';
  return 'LOW';
}

export function confidenceLabelFromScore(score?: unknown) {
  const code = confidenceCodeFromScore(score);
  return code ? confidenceLabel(code) : 'Indefinida';
}

export function confidenceIsDivergent(score?: unknown, label?: unknown) {
  const expected = confidenceCodeFromScore(score);
  const informed = normalizedLabel(label);
  return Boolean(expected && informed && expected !== informed);
}

export function trendConfidenceLabel(label?: unknown) {
  return ({ HIGH: 'Alta', MEDIUM: 'Média', LOW: 'Baixa', VERY_LOW: 'Muito baixa', UNKNOWN: 'Indefinida' } as Record<string, string>)[normalizedLabel(label, 'UNKNOWN')] ?? 'Indefinida';
}

export function explanationQualityLabel(label?: unknown) {
  return ({ STRONG: 'Robusta', GOOD: 'Boa', BASIC: 'Básica' } as Record<string, string>)[normalizedLabel(label)] ?? 'Indefinida';
}

export function riskLabel(level?: unknown) {
  return ({ LOW: 'Baixo', MEDIUM: 'Médio', HIGH: 'Alto', UNKNOWN: 'Indefinido' } as Record<string, string>)[normalizedLabel(level, 'UNKNOWN')] ?? 'Indefinido';
}

export function riskTone(level?: unknown): VisualTone {
  return ({ LOW: 'success', MEDIUM: 'warning', HIGH: 'danger', UNKNOWN: 'neutral' } as Record<string, VisualTone>)[normalizedLabel(level, 'UNKNOWN')] ?? 'neutral';
}

export function appreciationLabel(signal?: unknown) {
  return ({ HIGH: 'Alto', MODERATE: 'Moderado', LOW: 'Baixo', UNKNOWN: 'Indefinido' } as Record<string, string>)[normalizedLabel(signal, 'UNKNOWN')] ?? 'Indefinido';
}

export function appreciationTone(signal?: unknown): VisualTone {
  return ({ HIGH: 'success', MODERATE: 'warning', LOW: 'danger', UNKNOWN: 'neutral' } as Record<string, VisualTone>)[normalizedLabel(signal, 'UNKNOWN')] ?? 'neutral';
}

export function trendLabel(label?: unknown) {
  return ({
    UPTREND: 'Tendência de alta',
    SIDEWAYS: 'Mercado lateral',
    DOWNTREND: 'Tendência de baixa',
    INSUFFICIENT_HISTORY: 'Histórico insuficiente',
  } as Record<string, string>)[normalizedLabel(label)] ?? 'Tendência indefinida';
}

export function trendDescription(label?: unknown) {
  return ({
    UPTREND: 'Ativo em tendência de alta, com sinal técnico favorável.',
    SIDEWAYS: 'Mercado lateral. O ativo permanece saudável, mas ainda sem força clara de valorização.',
    DOWNTREND: 'Ativo em tendência de baixa. Pode ser melhor aguardar reversão.',
    INSUFFICIENT_HISTORY: 'Ainda não há histórico suficiente para leitura confiável.',
  } as Record<string, string>)[normalizedLabel(label)] ?? 'A API não retornou uma leitura de tendência conclusiva.';
}

export function trendTone(label?: unknown): VisualTone {
  return ({ UPTREND: 'success', SIDEWAYS: 'warning', DOWNTREND: 'danger', INSUFFICIENT_HISTORY: 'neutral' } as Record<string, VisualTone>)[normalizedLabel(label)] ?? 'neutral';
}

export function percentileLabel(label?: unknown) {
  return ({
    TOP_5_PERCENT: 'Top 5%',
    TOP_10_PERCENT: 'Top 10%',
    TOP_25_PERCENT: 'Top 25%',
    TOP_50_PERCENT: 'Top 50%',
    BOTTOM_50_PERCENT: 'Faixa inferior de 50%',
    UNKNOWN: 'Posição indefinida',
  } as Record<string, string>)[normalizedLabel(label, 'UNKNOWN')] ?? (typeof label === 'string' ? label : 'Posição indefinida');
}

export function percentileTone(label?: unknown): VisualTone {
  return ({
    TOP_5_PERCENT: 'success',
    TOP_10_PERCENT: 'success',
    TOP_25_PERCENT: 'success',
    TOP_50_PERCENT: 'warning',
    BOTTOM_50_PERCENT: 'danger',
    UNKNOWN: 'neutral',
  } as Record<string, VisualTone>)[normalizedLabel(label, 'UNKNOWN')] ?? 'neutral';
}

export function suggestedAction(item: BudgetRecommendation): SuggestedAction {
  const status = normalizedLabel(item.status);
  const risk = normalizedLabel(item.risk_level, 'UNKNOWN');
  const appreciation = normalizedLabel(item.appreciation_signal ?? item.decision_card?.appreciation_signal, 'UNKNOWN');
  const recommendation = normalized(item.recommendation_score ?? item.decision_card?.recommendation_score) ?? 0;
  const confidence = normalized(item.confidence_score ?? item.decision_card?.confidence_score) ?? 0;
  const trend = normalizedLabel(item.trend_label);
  const momentum = normalized(item.momentum_score);
  const confidenceReading = normalizedLabel(item.confidence_label);

  if (risk === 'HIGH' || status === 'BLOCKED' || appreciation === 'LOW') {
    return { label: 'Evitar', tone: 'danger', reason: 'Há um bloqueio, risco alto ou baixo potencial quantitativo.' };
  }

  if (trend === 'DOWNTREND') {
    return { label: 'Aguardar', tone: 'warning', reason: 'A tendência de baixa pede confirmação de reversão antes de investir.' };
  }

  if (trend === 'SIDEWAYS') {
    const detail = momentum === null ? 'sem leitura de momentum' : `com momentum em ${scoreText(momentum)}`;
    return { label: 'Aguardar', tone: 'warning', reason: `Mercado lateral ${detail}; aguarde um sinal direcional mais claro.` };
  }

  if (trend !== 'UPTREND') {
    return { label: 'Aguardar', tone: 'warning', reason: 'A tendência ainda não possui histórico suficiente para sustentar uma compra.' };
  }

  if (appreciation === 'UNKNOWN') {
    return { label: 'Aguardar', tone: 'warning', reason: 'O potencial de valorização ainda não foi definido pela análise.' };
  }

  if (confidenceReading === 'LOW') {
    return { label: 'Aguardar', tone: 'warning', reason: 'O nível de confiança informado é baixo e pede nova confirmação.' };
  }

  if (status === 'APPROVED' && risk === 'LOW' && recommendation >= 75 && confidence >= 80) {
    return { label: 'Comprar', tone: 'success', reason: 'Aprovado, com risco baixo e scores consistentes.' };
  }

  return { label: 'Aguardar', tone: 'warning', reason: 'Os sinais ainda não atendem a todos os critérios de compra.' };
}

export function opportunityRating(
  recommendation?: unknown,
  confidence?: unknown,
  action?: SuggestedAction['label'],
): OpportunityRating {
  const recommendationScore = normalized(recommendation);
  const confidenceScore = normalized(confidence);
  if (recommendationScore === null || confidenceScore === null) {
    return { stars: 0, label: 'Rating indisponível', compositeScore: null, tone: 'neutral' };
  }
  const compositeScore = (recommendationScore + confidenceScore) / 2;

  // A leitura visual não pode contradizer a ação exibida no mesmo card.
  if (action === 'Evitar') return { stars: 1, label: 'Evitar', compositeScore, tone: 'danger' };
  if (action === 'Aguardar') return { stars: 2, label: 'Aguardar', compositeScore, tone: 'warning' };
  if (compositeScore >= 90) return { stars: 5, label: 'Excelente oportunidade', compositeScore, tone: 'success' };
  if (compositeScore >= 80) return { stars: 4, label: 'Boa oportunidade', compositeScore, tone: 'success' };
  if (compositeScore >= 70) return { stars: 3, label: 'Oportunidade moderada', compositeScore, tone: 'warning' };
  if (compositeScore >= 60) return { stars: 2, label: 'Aguardar', compositeScore, tone: 'warning' };
  return { stars: 1, label: 'Evitar', compositeScore, tone: 'danger' };
}

export function decisionPresentation(item: BudgetRecommendation): DecisionPresentation {
  const action = suggestedAction(item);
  const decision = item.decision_card ?? {};
  const rating = opportunityRating(
    item.recommendation_score ?? decision.recommendation_score,
    item.confidence_score ?? decision.confidence_score,
    action.label,
  );

  if (action.label === 'Comprar') {
    return {
      action,
      rating,
      tone: 'success',
      eyebrow: 'Melhor oportunidade para os filtros',
      headline: 'Os sinais atuais sustentam uma decisão de compra.',
    };
  }
  if (action.label === 'Evitar') {
    return {
      action,
      rating,
      tone: 'danger',
      eyebrow: 'Compra não indicada neste cenário',
      headline: 'Os bloqueios atuais superam os sinais positivos do ativo.',
    };
  }
  return {
    action,
    rating,
    tone: 'warning',
    eyebrow: 'Oportunidade em observação',
    headline: 'Os sinais ainda pedem confirmação antes de investir.',
  };
}
