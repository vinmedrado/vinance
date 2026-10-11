import { formatCurrency, formatPercent } from '../../../utils/formatters';
import type { MoneyValue, RankedInvestmentOpportunity } from '../types/financialState.types';

function known(value: unknown): boolean {
  return value !== null && value !== undefined && value !== '';
}

function dateLabel(value: string | null | undefined): string {
  if (!value) return 'Não informado';
  const [year, month, day] = value.slice(0, 10).split('-');
  return year && month && day ? `${day}/${month}/${year}` : value;
}

function moneyLabel(value: MoneyValue | undefined): string {
  return known(value) ? formatCurrency(value) : 'Não informado';
}

function rateLabel(value: MoneyValue | undefined): string {
  return known(value) ? `${formatPercent(value)} a.a.` : 'Não informada';
}

function liquidityLabel(value: string | null | undefined): string {
  if (value === 'DAILY_REPURCHASE') return 'Recompra diária a preço de mercado';
  if (value === 'DAILY_LIQUIDITY') return 'Liquidez diária';
  return value || 'Não informada';
}

function guaranteeLabel(value: string | null | undefined): string {
  if (value === 'SOVEREIGN_ISSUER') return 'Emissor soberano — não é FGC';
  return value || 'Não informada';
}

function productTypeLabel(value: string | null | undefined): string {
  const labels: Record<string, string> = {
    TREASURY_SELIC: 'Tesouro Selic',
    TREASURY_PREFIXED: 'Tesouro Prefixado',
    TREASURY_IPCA: 'Tesouro IPCA+',
    TREASURY_RENDA_PLUS: 'Tesouro RendA+',
    TREASURY_EDUCA_PLUS: 'Tesouro Educa+',
    TREASURY_OTHER: 'Tesouro',
  };
  return value ? labels[value] ?? value : 'Não informado';
}

function freshnessLabel(value: string | null | undefined): string {
  if (value === 'FRESH') return 'Dados atuais';
  if (value === 'STALE') return 'Dados desatualizados';
  return 'Atualidade desconhecida';
}

export function FixedIncomeOpportunityDetails({
  opportunity,
}: {
  opportunity: RankedInvestmentOpportunity;
}) {
  if (opportunity.market !== 'FIXED_INCOME') return null;

  return (
    <div className="vn-grid vn-grid--two" aria-label={`Detalhes de renda fixa de ${opportunity.product_name ?? opportunity.symbol}`}>
      <div><small>Tipo e indexador</small><strong>{productTypeLabel(opportunity.product_type)} · {opportunity.indexer || 'Não informado'}</strong></div>
      <div><small>Taxa de referência</small><strong>{rateLabel(opportunity.reference_rate)}</strong></div>
      <div><small>Vencimento</small><strong>{dateLabel(opportunity.maturity_date)}</strong></div>
      <div><small>Liquidez conhecida</small><strong>{liquidityLabel(opportunity.liquidity_type)}</strong></div>
      <div><small>Aporte mínimo</small><strong>{moneyLabel(opportunity.minimum_investment)}</strong></div>
      <div><small>Garantia</small><strong>{guaranteeLabel(opportunity.guarantee_type)}</strong></div>
      <div><small>Preço unitário de referência</small><strong>{moneyLabel(opportunity.price_reference)}</strong></div>
      <div><small>Dados de mercado</small><strong>{dateLabel(opportunity.market_date)} · {freshnessLabel(opportunity.freshness_status)}</strong></div>
      <p>Taxa e preço são referências usadas na decisão, não promessa de retorno nem garantia do preço de execução.</p>
    </div>
  );
}
