import type { CSSProperties } from 'react';
import { CircleDollarSign, Coins, WalletCards } from 'lucide-react';
import { Card } from '../../../components';
import type { BudgetRecommendation } from '../types/investmentWorkspace.types';
import { currencyText, decisionPresentation, numberValue, percentText, quantityText } from '../utils/investmentDecision';
import type { DecisionPresentation } from '../utils/investmentDecision';

export function BudgetUsageCard({ item, budget, presentation = decisionPresentation(item) }: { item: BudgetRecommendation; budget?: number | string; presentation?: DecisionPresentation }) {
  const decision = item.decision_card ?? {};
  const usageValue = decision.budget_usage_pct ?? item.budget_usage_pct;
  const usageNumber = numberValue(usageValue);
  const usage = Math.max(0, Math.min(100, usageNumber ?? 0));
  const progressStyle = { '--vn-progress': `${usage}%` } as CSSProperties;

  return (
    <Card className={`vn-budget-usage-card vn-budget-usage-card--${presentation.tone}`} title="Uso do orçamento" description={presentation.action.label === 'Comprar' ? 'Quanto da verba informada será convertido em posição.' : 'Simulação técnica preservada para comparação; não representa ordem de execução.'}>
      <div className="vn-budget-usage-card__amount">
        <span>{presentation.action.label === 'Comprar' ? 'Investimento sugerido' : 'Alocação calculada — não executar'}</span>
        <strong>{currencyText(decision.invested_amount ?? item.invested_amount)}</strong>
        <small>de {currencyText(budget)}</small>
      </div>
      <div className={`vn-budget-progress vn-budget-progress--${presentation.tone}`} style={progressStyle}>
        <div><span>Orçamento utilizado</span><strong>{percentText(usageValue)}</strong></div>
        <div
          className="vn-budget-progress__track"
          role="progressbar"
          aria-label="Uso do orçamento"
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={usageNumber === null ? undefined : usage}
          aria-valuetext={usageNumber === null ? 'Não informado' : undefined}
        ><span /></div>
      </div>
      <dl className="vn-compact-metrics vn-compact-metrics--budget">
        <div><dt><Coins size={16} aria-hidden="true" /> Quantidade</dt><dd>{quantityText(decision.quantity ?? item.quantity_possible)}</dd></div>
        <div><dt><WalletCards size={16} aria-hidden="true" /> Saldo livre</dt><dd>{currencyText(decision.remaining_budget ?? item.remaining_budget)}</dd></div>
        <div><dt><CircleDollarSign size={16} aria-hidden="true" /> Preço unitário</dt><dd>{currencyText(decision.price ?? item.price)}</dd></div>
      </dl>
    </Card>
  );
}
