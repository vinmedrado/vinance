import { History, MoveRight, TrendingDown, TrendingUp } from 'lucide-react';
import { Card } from '../../../components';
import type { BudgetRecommendation } from '../types/investmentWorkspace.types';
import { appreciationLabel, appreciationTone, decisionPresentation, scoreText, trendConfidenceLabel, trendDescription, trendLabel, trendTone } from '../utils/investmentDecision';
import type { DecisionPresentation } from '../utils/investmentDecision';

export function TrendInterpreterCard({ item, presentation = decisionPresentation(item) }: { item: BudgetRecommendation; presentation?: DecisionPresentation }) {
  const normalized = (item.trend_label ?? '').toUpperCase();
  const TrendIcon = normalized === 'UPTREND' ? TrendingUp : normalized === 'DOWNTREND' ? TrendingDown : normalized === 'SIDEWAYS' ? MoveRight : History;
  const trendColor = trendTone(item.trend_label ?? undefined);
  const appreciation = item.appreciation_signal ?? item.decision_card?.appreciation_signal;
  const potentialTone = appreciationTone(appreciation);

  return (
    <Card className="vn-trend-card" title="Tendência e potencial" description="Interpretação dos sinais técnicos já produzidos pela API.">
      <div className={`vn-trend-reading vn-trend-reading--${trendColor}`}>
        <div className="vn-trend-reading__icon"><TrendIcon size={22} aria-hidden="true" /></div>
        <div><strong>{trendLabel(item.trend_label ?? undefined)}</strong><p>{trendDescription(item.trend_label ?? undefined)}</p></div>
      </div>
      <div className="vn-trend-facts">
        <span>Momentum <strong>{scoreText(item.momentum_score)}</strong></span>
        <span>Confiança da tendência <strong>{trendConfidenceLabel(item.trend_confidence)}</strong></span>
      </div>
      <div className="vn-potential-block">
        <div><span>Potencial de valorização</span><strong className={`vn-potential-badge vn-potential-badge--${potentialTone}`}>{appreciationLabel(appreciation)}</strong></div>
        <p>{item.appreciation_text ?? 'Potencial não informado pela API.'}</p>
        {presentation.action.label !== 'Comprar' && <p className={`vn-signal-context vn-signal-context--${presentation.tone}`}>{presentation.action.reason}</p>}
      </div>
    </Card>
  );
}
