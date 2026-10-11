import { render, screen } from '@testing-library/react';
import { expect, test } from 'vitest';

import { FixedIncomeOpportunityDetails } from '../../src/features/financial-state/components/FixedIncomeOpportunityDetails';
import type { RankedInvestmentOpportunity } from '../../src/features/financial-state/types/financialState.types';

const opportunity: RankedInvestmentOpportunity = {
  asset_id: 31,
  symbol: 'Tesouro Selic 2031',
  ticker: 'TD-TEST',
  asset_class: 'FIXED_INCOME',
  market: 'FIXED_INCOME',
  action: 'BUY',
  rank: 1,
  price_reference: '15000.00',
  quantity_candidate: 0,
  quantity_suggested: 0,
  capital_required: '150.00',
  capital_committed: '1000.00',
  recommendation_score: '100',
  risk_level: 'LOW',
  trend_label: null,
  momentum_score: null,
  confidence: '90',
  guardrail_status: 'APPROVED',
  reasons: [],
  warnings: [],
  reason: 'Produto compatível com os dados conhecidos.',
  product_name: 'Tesouro Selic 2031',
  product_type: 'TREASURY_SELIC',
  indexer: 'SELIC',
  reference_rate: '0.05',
  maturity_date: '2031-03-01',
  liquidity_type: 'DAILY_REPURCHASE',
  minimum_investment: '150.00',
  guarantee_type: 'SOVEREIGN_ISSUER',
  market_date: '2026-10-09',
  freshness_status: 'FRESH',
};

test('presents frozen fixed-income facts without calculating a recommendation', () => {
  render(<FixedIncomeOpportunityDetails opportunity={opportunity} />);

  expect(screen.getByText('Tesouro Selic · SELIC')).toBeInTheDocument();
  expect(screen.getByText('0,05% a.a.')).toBeInTheDocument();
  expect(screen.getByText('01/03/2031')).toBeInTheDocument();
  expect(screen.getByText('Recompra diária a preço de mercado')).toBeInTheDocument();
  expect(screen.getByText('Emissor soberano — não é FGC')).toBeInTheDocument();
  expect(screen.getByText(/não promessa de retorno/i)).toBeInTheDocument();
});

test('shows stale and missing facts explicitly instead of inventing values', () => {
  render(
    <FixedIncomeOpportunityDetails
      opportunity={{
        ...opportunity,
        action: 'WAIT',
        freshness_status: 'STALE',
        reference_rate: null,
        minimum_investment: null,
        guarantee_type: null,
      }}
    />,
  );

  expect(screen.getByText(/09\/10\/2026.*Dados desatualizados/)).toBeInTheDocument();
  expect(screen.getAllByText('Não informada').length).toBeGreaterThan(0);
  expect(screen.getAllByText('Não informado').length).toBeGreaterThan(0);
  expect(screen.queryByText('R$ 0,00')).not.toBeInTheDocument();
});

test('does not render fixed-income fields for another market', () => {
  const { container } = render(
    <FixedIncomeOpportunityDetails opportunity={{ ...opportunity, market: 'ETF' }} />,
  );

  expect(container).toBeEmptyDOMElement();
});
