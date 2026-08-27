import type { CSSProperties } from 'react';
import { BarChart3, BadgeCheck, Gauge } from 'lucide-react';
import { Card } from '../../../components';
import type { BudgetRecommendation } from '../types/investmentWorkspace.types';
import { confidenceIsDivergent, confidenceLabel, confidenceLabelFromScore, decisionPresentation, explanationQualityLabel, numberValue, quantitativeChance, scoreText, scoreTone } from '../utils/investmentDecision';
import type { DecisionPresentation } from '../utils/investmentDecision';

export function QuantChanceCard({ item, presentation = decisionPresentation(item) }: { item: BudgetRecommendation; presentation?: DecisionPresentation }) {
  const decision = item.decision_card ?? {};
  const recommendationValue = item.recommendation_score ?? decision.recommendation_score;
  const confidenceValue = item.confidence_score ?? decision.confidence_score;
  const recommendationScore = numberValue(recommendationValue);
  const chance = recommendationScore === null ? 'Indefinida' : quantitativeChance(recommendationScore);
  const tone = scoreTone(recommendationScore);
  const confidenceDivergent = confidenceIsDivergent(confidenceValue, item.confidence_label);
  const resolvedConfidenceLabel = numberValue(confidenceValue) === null ? confidenceLabel(item.confidence_label) : confidenceLabelFromScore(confidenceValue);
  const gaugeStyle = { '--vn-score': `${Math.max(0, Math.min(100, recommendationScore ?? 0))}%` } as CSSProperties;

  return (
    <Card className="vn-quant-chance-card" title="Chance quantitativa" description="Leitura simples do score calculado pelo Recommendation Engine.">
      <div className="vn-quant-chance-card__main">
        <div
          className={`vn-score-gauge vn-score-gauge--${tone}`}
          style={gaugeStyle}
          role={recommendationScore === null ? undefined : 'meter'}
          aria-label={recommendationScore === null ? 'Recommendation Score não informado' : 'Recommendation Score'}
          aria-valuemin={recommendationScore === null ? undefined : 0}
          aria-valuemax={recommendationScore === null ? undefined : 100}
          aria-valuenow={recommendationScore === null ? undefined : Math.max(0, Math.min(100, recommendationScore))}
        >
          <span>{scoreText(recommendationValue)}</span>
          <small>/ 100</small>
        </div>
        <div><span className="vn-kicker">Chance estimada</span><strong className={`vn-score-reading vn-score-reading--${tone}`}>{chance}</strong><p>Indicador quantitativo, sem garantia de retorno.</p></div>
      </div>
      <dl className="vn-compact-metrics">
        <div><dt><Gauge size={16} aria-hidden="true" /> Confidence Score</dt><dd>{scoreText(confidenceValue)}</dd></div>
        <div><dt><BarChart3 size={16} aria-hidden="true" /> Nível de confiança</dt><dd>{resolvedConfidenceLabel}</dd></div>
        <div><dt><BadgeCheck size={16} aria-hidden="true" /> Qualidade da explicação</dt><dd>{explanationQualityLabel(item.explanation_quality)}</dd></div>
      </dl>
      {confidenceDivergent && <p className="vn-data-divergence" role="status">Dados de confiança divergentes: o nível exibido foi derivado do score numérico validado.</p>}
      {presentation.action.label !== 'Comprar' && tone === 'success' && (
        <p className={`vn-signal-context vn-signal-context--${presentation.tone}`} role="note">
          Score quantitativo alto, mas a decisão permanece {presentation.action.label}: {presentation.action.reason}
        </p>
      )}
    </Card>
  );
}
