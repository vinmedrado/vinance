import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { ActionPlanCard } from '../../src/features/financial-state/components/ActionPlanCard';
import type {
  ActionPlan,
  ActionPlanActionType,
  ActionPlanItem,
  ActionPlanStatus,
} from '../../src/features/financial-state/types/financialState.types';

const generatedAt = '2026-09-23T12:00:00Z';

function action(
  actionType: ActionPlanActionType,
  rank: number,
  amount: string | null,
): ActionPlanItem {
  const investment = actionType.startsWith('INVESTMENT_');
  return {
    action_id: `action-${rank}`,
    category: actionType === 'HOLD_CASH'
      ? 'HOLD'
      : actionType === 'COMPLETE_INFORMATION'
        ? 'INFORMATION'
        : investment ? 'INVESTMENT' : 'FINANCIAL',
    action_type: actionType,
    priority_rank: rank,
    title: actionType === 'GOAL_CONTRIBUTION' ? 'Viagem' : actionType.replace(/_/g, ' '),
    description: 'Decisão derivada da cadeia congelada.',
    ownership_scope: investment || actionType === 'HOLD_CASH' ? 'HOUSEHOLD' : 'PERSONAL',
    owner_user_id: investment ? null : 1,
    household_id: 10,
    currency: amount === null ? null : 'BRL',
    amount,
    target_amount: amount,
    remaining_need: actionType === 'GOAL_CONTRIBUTION' ? '2700.00' : null,
    liability_id: actionType === 'DEBT_PAYMENT' ? 4 : null,
    goal_id: actionType === 'GOAL_CONTRIBUTION' ? 8 : null,
    asset_id: investment ? 22 : null,
    symbol: investment ? 'ETF11' : null,
    asset_class: investment ? 'ETF' : null,
    quantity_candidate: actionType === 'INVESTMENT_BUY' ? 2 : null,
    price_reference: investment ? '96.50' : null,
    price_timestamp: investment ? generatedAt : null,
    price_source: investment ? 'vinance_score_v1' : null,
    freshness_status: investment ? 'FRESH' : null,
    action_status: actionType === 'INVESTMENT_BUY'
      ? 'ACTIONABLE'
      : actionType === 'INVESTMENT_AVOID'
        ? 'AVOID'
        : actionType === 'INVESTMENT_WAIT' || actionType === 'HOLD_CASH'
          ? 'WAIT'
          : actionType === 'COMPLETE_INFORMATION'
            ? 'INFORMATIONAL'
            : 'ACTIONABLE',
    severity: actionType === 'INVESTMENT_AVOID' ? 'WARNING' : 'INFO',
    reason: 'Motivo verificável do backend.',
    evidence: [],
    warnings: [],
    blockers: [],
    missing_information: [],
    source_engine: investment ? 'investment-orchestrator-v1' : 'capital-allocation-v1',
    source_decision_id: investment ? 31 : 23,
    source_reference: {},
    generated_at: generatedAt,
  };
}

function plan(status: ActionPlanStatus = 'READY'): ActionPlan {
  const actions = [
    action('GOAL_CONTRIBUTION', 1, '300.00'),
    action('INVESTMENT_BUY', 2, '193.00'),
    action('INVESTMENT_WAIT', 3, null),
    action('INVESTMENT_AVOID', 4, null),
    action('HOLD_CASH', 5, '140.00'),
  ];
  return {
    action_plan_id: 41,
    household_id: 10,
    financial_state_snapshot_id: 7,
    financial_policy_decision_id: 17,
    capital_allocation_decision_id: 23,
    investment_orchestration_decision_id: 31,
    engine_version: 'action-plan-v1',
    rules_version: 'action-plan-rules-v1',
    status,
    currency: 'BRL',
    period: 'MONTHLY',
    summary: {
      authorized_financial_capital: '300.00',
      authorized_investment_capital: '333.00',
      financial_actions_total: '300.00',
      investment_buy_total: '193.00',
      hold_cash_total: '140.00',
      action_count: actions.length,
      primary_action: 'Avance no objetivo Viagem',
    },
    actions,
    information_actions: [],
    financial_actions: actions.slice(0, 1),
    investment_actions: actions.slice(1, 4),
    hold_actions: actions.slice(4),
    total_financial_actions: '300.00',
    total_investment_actions: '193.00',
    total_hold_cash: '140.00',
    speculative_capital: '0.00',
    trading_dispatch: false,
    blockers: [],
    warnings: [],
    missing_information: [],
    evidence: [],
    rule_traces: [],
    state_fingerprint: 'a'.repeat(64),
    policy_fingerprint: 'b'.repeat(64),
    allocation_fingerprint: 'c'.repeat(64),
    orchestration_fingerprint: 'd'.repeat(64),
    ruleset_fingerprint: 'e'.repeat(64),
    decision_fingerprint: 'f'.repeat(64),
    generated_at: generatedAt,
    created_at: generatedAt,
  };
}

const baseProps = {
  history: { items: [], total: 0 },
  isLoading: false,
  onRetry: vi.fn(),
  onRetryHistory: vi.fn(),
  onFreeze: vi.fn(),
  onSelectHistory: vi.fn(),
  onShowCurrent: vi.fn(),
};

describe('ActionPlanCard', () => {
  it('renders loading and API error business states', async () => {
    const user = userEvent.setup();
    const retry = vi.fn();
    const { rerender } = render(<ActionPlanCard {...baseProps} isLoading />);
    expect(screen.getByText('Organizando o que fazer agora...')).toBeInTheDocument();
    rerender(<ActionPlanCard {...baseProps} errorMessage="Falha controlada" onRetry={retry} />);
    expect(screen.getByText('Não foi possível montar seu plano')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Tentar novamente' }));
    expect(retry).toHaveBeenCalledOnce();
  });

  it('shows ordered financial, BUY, WAIT, AVOID and HOLD actions without execution CTA', () => {
    render(<ActionPlanCard {...baseProps} plan={plan()} />);
    expect(screen.getByText('PRONTO')).toBeInTheDocument();
    expect(screen.getByText('Ver recomendação de compra')).toBeInTheDocument();
    expect(screen.getByText('Aguardar')).toBeInTheDocument();
    expect(screen.getByText('Evitar')).toBeInTheDocument();
    expect(screen.getByText('Manter em caixa')).toBeInTheDocument();
    expect(screen.getAllByText(/Não é garantia do preço de execução/)).toHaveLength(3);
    expect(screen.queryByText('Comprar agora')).not.toBeInTheDocument();
    const link = screen.getAllByRole('link', { name: 'Ver oportunidade em Investir' })[0];
    expect(link).toHaveAttribute(
      'href',
      expect.stringContaining('decision_id=31&action_plan_id=41&asset_id=22'),
    );
  });

  it.each([
    ['BLOCKED', 'Ainda não é possível montar um plano seguro'],
    ['PARTIAL', 'Existe um plano parcial. Algumas ações dependem de informações adicionais.'],
    ['NO_ACTION_REQUIRED', 'Nenhuma ação nova é necessária neste momento.'],
  ] as const)('renders %s as a normal business state', (status, message) => {
    render(<ActionPlanCard {...baseProps} plan={plan(status)} />);
    expect(screen.getByText(message)).toBeInTheDocument();
  });

  it('opens frozen history and labels historical prices as frozen', async () => {
    const user = userEvent.setup();
    const select = vi.fn();
    const frozen = plan('PARTIAL');
    render(
      <ActionPlanCard
        {...baseProps}
        plan={frozen}
        isHistorical
        onSelectHistory={select}
        history={{
          total: 1,
          items: [{
            action_plan_id: 41,
            household_id: 10,
            financial_state_snapshot_id: 7,
            financial_policy_decision_id: 17,
            capital_allocation_decision_id: 23,
            investment_orchestration_decision_id: 31,
            engine_version: 'action-plan-v1',
            rules_version: 'action-plan-rules-v1',
            status: 'PARTIAL',
            currency: 'BRL',
            period: 'MONTHLY',
            primary_action: 'Avance no objetivo Viagem',
            action_titles: ['Viagem', 'ETF11'],
            action_count: 5,
            investment_budget: '333.00',
            total_financial_actions: '300.00',
            total_investment_actions: '193.00',
            total_hold_cash: '140.00',
            decision_fingerprint: 'f'.repeat(64),
            generated_at: generatedAt,
            created_at: generatedAt,
          }],
        }}
      />,
    );
    expect(screen.getByText('PLANO CONGELADO')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Ver plano congelado' }));
    expect(select).toHaveBeenCalledWith(41);
  });

  it('shows missing information without turning it into a monetary amount', () => {
    const partial = plan('PARTIAL');
    const info = action('COMPLETE_INFORMATION', 1, null);
    partial.actions = [info];
    partial.information_actions = [info];
    partial.financial_actions = [];
    partial.investment_actions = [];
    partial.hold_actions = [];
    partial.missing_information = [{
      code: 'PROFILE_REQUIRED',
      message: 'Complete seu perfil de investidor.',
      fields: ['financial_profiles.risk_profile'],
      rule_ids: ['APV1-INFORMATION-001'],
    }];
    render(<ActionPlanCard {...baseProps} plan={partial} />);
    expect(screen.getByText('Complete seu perfil de investidor.')).toBeInTheDocument();
    expect(screen.getByText(/Valor não informado/)).toBeInTheDocument();
  });
});
