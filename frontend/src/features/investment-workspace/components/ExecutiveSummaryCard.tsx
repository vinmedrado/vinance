import { Award, ListOrdered } from 'lucide-react';
import { Card } from '../../../components';
import type { BudgetRecommendation } from '../types/investmentWorkspace.types';
import { decisionPresentation, percentileLabel, percentileTone, quantityText } from '../utils/investmentDecision';
import type { DecisionPresentation } from '../utils/investmentDecision';

export function ExecutiveSummaryCard({ item, presentation = decisionPresentation(item) }: { item: BudgetRecommendation; presentation?: DecisionPresentation }) {
  const relative = item.relative_position;
  const engineSummary = item.executive_summary ?? item.decision_summary;

  return (
    <Card className={`vn-executive-card vn-executive-card--${presentation.tone}`} title="Resumo executivo" description="A decisão em linguagem direta, com sua posição no ranking.">
      <p className={`vn-executive-card__decision vn-executive-card__decision--${presentation.tone}`}>{presentation.headline}</p>
      {presentation.action.label === 'Comprar' ? (
        <p className="vn-executive-card__summary">{engineSummary ?? 'A API não retornou um resumo executivo.'}</p>
      ) : engineSummary ? (
        <details className="vn-engine-context">
          <summary>Contexto técnico original da API — não altera a decisão visual</summary>
          <p>{engineSummary}</p>
        </details>
      ) : (
        <p className="vn-executive-card__summary">A API não retornou um resumo executivo.</p>
      )}
      {relative ? (
        <div className="vn-relative-ranking">
          <div><ListOrdered size={19} aria-hidden="true" /><span>Posição<strong>{quantityText(relative.rank)}</strong></span></div>
          <div><Award size={19} aria-hidden="true" /><span>Entre candidatos<strong>{quantityText(relative.total_candidates)}</strong></span></div>
          <div className={`vn-relative-ranking__label vn-relative-ranking__label--${percentileTone(relative.percentile_label)}`}><span>{percentileLabel(relative.percentile_label)}</span></div>
          <p>{relative.text ?? 'Posição relativa calculada pela API.'}</p>
        </div>
      ) : (
        <div className="vn-decision-empty"><ListOrdered size={19} aria-hidden="true" /><span>Ranking relativo não informado pela API.</span></div>
      )}
    </Card>
  );
}
