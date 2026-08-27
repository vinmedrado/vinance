import { Clock3, ShoppingCart, Sparkles, ShieldX } from 'lucide-react';
import { Card } from '../../../components';
import type { BudgetRecommendation } from '../types/investmentWorkspace.types';
import { currencyText, decisionPresentation, numberValue, quantityText } from '../utils/investmentDecision';
import type { DecisionPresentation } from '../utils/investmentDecision';
import { OpportunityRatingBadge } from './OpportunityRatingBadge';
import { RiskBadge } from './RiskBadge';

export function DecisionHeroCard({ item, presentation = decisionPresentation(item) }: { item: BudgetRecommendation; presentation?: DecisionPresentation }) {
  const decision = item.decision_card ?? {};
  const action = presentation.action;
  const ActionIcon = action.label === 'Comprar' ? ShoppingCart : action.label === 'Evitar' ? ShieldX : Clock3;
  const quantity = decision.quantity ?? item.quantity_possible;
  const price = decision.price ?? item.price;
  const invested = decision.invested_amount ?? item.invested_amount;
  const remaining = decision.remaining_budget ?? item.remaining_budget;
  const quantityNumber = numberValue(quantity);
  const quantityUnit = quantityNumber !== null && Math.trunc(quantityNumber) === 1 ? 'cota' : 'cotas';

  return (
    <Card className={`vn-decision-hero vn-decision-hero--${presentation.tone}`}>
      <div className="vn-decision-hero__topline">
        <span className="vn-decision-hero__eyebrow"><Sparkles size={16} aria-hidden="true" /> {presentation.eyebrow}</span>
        <div className="vn-decision-hero__context">
          <span className="vn-market-chip">{item.market || 'Mercado não informado'}</span>
          <RiskBadge level={item.risk_level} />
        </div>
      </div>

      <div className="vn-decision-hero__headline">
        <div>
          <h2>{item.ticker}</h2>
          <p className="vn-decision-hero__summary">{presentation.headline}</p>
          {presentation.action.label === 'Comprar' && item.recommendation_title && <p className="vn-decision-hero__engine-copy">Leitura técnica da API: {item.recommendation_title}</p>}
        </div>
        <OpportunityRatingBadge rating={presentation.rating} />
      </div>

      <div className={`vn-action-callout vn-action-callout--${action.tone}`}>
        <span><ActionIcon size={18} aria-hidden="true" /> {action.label}</span>
        <p>{action.reason}</p>
      </div>

      <div className="vn-decision-hero__metrics">
        <div><span>{action.label === 'Comprar' ? 'Quantidade sugerida' : 'Quantidade calculada'}</span><strong>{quantityText(quantity)} {quantityUnit}</strong></div>
        <div><span>Preço atual</span><strong>{currencyText(price)}</strong></div>
        <div><span>{action.label === 'Comprar' ? 'Valor a investir' : 'Alocação calculada'}</span><strong>{currencyText(invested)}</strong></div>
        <div><span>Saldo restante</span><strong>{currencyText(remaining)}</strong></div>
      </div>
    </Card>
  );
}
