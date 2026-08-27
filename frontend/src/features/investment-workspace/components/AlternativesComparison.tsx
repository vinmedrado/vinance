import { ArrowDownRight, ArrowRight, ArrowUpRight, GitCompareArrows, History, Layers3 } from 'lucide-react';
import { Card } from '../../../components';
import type { AlternativeComparison, BudgetRecommendation } from '../types/investmentWorkspace.types';
import { currencyText, decisionPresentation, quantityText, scoreText, trendLabel, trendTone } from '../utils/investmentDecision';
import { RiskBadge } from './RiskBadge';

type AlternativesComparisonProps = {
  comparison?: AlternativeComparison[];
  alternatives?: BudgetRecommendation[];
};

export function AlternativesComparison({ comparison, alternatives }: AlternativesComparisonProps) {
  const topAlternatives = (alternatives ?? []).slice(0, 10);

  return (
    <div className="vn-alternatives-stack">
      <Card className="vn-comparison-card" title="Por que ficou acima das alternativas" description="Comparação direta retornada para a recomendação principal.">
        {comparison && comparison.length > 0 ? (
          <div className="vn-comparison-list">
            {comparison.map((alternative, index) => (
              <article key={`${index}-${alternative.ticker}-${alternative.reason}`}>
                <span className="vn-comparison-list__icon"><GitCompareArrows size={17} aria-hidden="true" /></span>
                <div><strong>{alternative.ticker || 'Ativo não informado'}</strong><p>{alternative.reason || 'Motivo não informado pela API.'}</p></div>
              </article>
            ))}
          </div>
        ) : (
          <div className="vn-decision-empty"><GitCompareArrows size={19} aria-hidden="true" /><span>Nenhuma comparação detalhada foi retornada.</span></div>
        )}
      </Card>

      <Card className="vn-alternatives-card" title="Outros ativos avaliados" description="As dez alternativas seguintes no ranking para o mesmo orçamento e perfil." action={<span className="vn-alternatives-count">Top {topAlternatives.length}</span>}>
        {topAlternatives.length > 0 ? (
          <div className="vn-alternative-grid">
            {topAlternatives.map((item, index) => {
              const rank = item.relative_position?.rank;
              const rankText = rank ?? '—';
              const presentation = decisionPresentation(item);
              const normalizedTrend = (item.trend_label ?? '').toUpperCase();
              const localTrendTone = trendTone(item.trend_label);
              const TrendIcon = normalizedTrend === 'UPTREND' ? ArrowUpRight : normalizedTrend === 'DOWNTREND' ? ArrowDownRight : normalizedTrend === 'SIDEWAYS' ? ArrowRight : History;
              return (
                <article className={`vn-alternative-item vn-alternative-item--${presentation.tone}`} key={`${rankText}-${item.ticker}-${index}`} aria-label={rank ? `Alternativa ${rank}: ${item.ticker}` : `Alternativa sem posição informada: ${item.ticker}`}>
                  <div className="vn-alternative-item__header">
                    <span className="vn-rank-number">#{rankText}</span>
                    <div><strong>{item.ticker}</strong><small>{item.market}</small></div>
                    <RiskBadge level={item.risk_level} showPrefix={false} />
                  </div>
                  <span className={`vn-alternative-action vn-alternative-action--${presentation.tone}`}>{presentation.action.label}</span>
                  <div className="vn-alternative-item__scores">
                    <span>Recomendação<strong>{scoreText(item.recommendation_score)}</strong></span>
                    <span>Confiança<strong>{scoreText(item.confidence_score)}</strong></span>
                  </div>
                  <div className={`vn-alternative-item__trend vn-alternative-item__trend--${localTrendTone}`}><TrendIcon size={15} aria-hidden="true" /><span>{trendLabel(item.trend_label ?? undefined)}</span></div>
                  <dl>
                    <div><dt>Cotas</dt><dd>{quantityText(item.quantity_possible)}</dd></div>
                    <div><dt>Investimento</dt><dd>{currencyText(item.invested_amount)}</dd></div>
                  </dl>
                </article>
              );
            })}
          </div>
        ) : (
          <div className="vn-decision-empty"><Layers3 size={19} aria-hidden="true" /><span>A API retornou apenas a recomendação principal.</span></div>
        )}
      </Card>
    </div>
  );
}
