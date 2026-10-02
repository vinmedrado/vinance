import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { ContinuousAutopilotCard } from '../../src/features/financial-state/components/ContinuousAutopilotCard';
import type {
  ContinuousAutopilot,
  ContinuousAutopilotStatus,
} from '../../src/features/financial-state/types/financialState.types';

const observedAt = '2026-09-29T20:00:00Z';

function decision(status: ContinuousAutopilotStatus = 'UNCHANGED'): ContinuousAutopilot {
  return {
    continuous_decision_id: 51,
    household_id: 10,
    previous_action_plan_id: 40,
    current_action_plan_id: 41,
    engine_version: 'continuous-autopilot-v1',
    rules_version: 'continuous-autopilot-rules-v1',
    status,
    materiality: status === 'CHANGED' ? 'HIGH' : 'NONE',
    alert_decision: status === 'CHANGED' ? 'IMPORTANT' : 'NO_ALERT',
    reevaluation_scope: status === 'CHANGED' ? 'FULL_CHAIN' : 'NONE',
    change_categories: status === 'CHANGED' ? ['FINANCIAL_DATA'] : [],
    detected_changes: status === 'CHANGED' ? [{
      change_id: 'income-changed',
      change_type: 'VALUE_CHANGED',
      category: 'FINANCIAL_DATA',
      entity_type: 'financial_state',
      entity_id: 7,
      previous_value: '5000.00',
      current_value: '4000.00',
      delta: '-1000.00',
      delta_percent: '-20.00',
      severity: 'IMPORTANT',
      materiality: 'HIGH',
      reason: 'A capacidade financeira mensal mudou.',
      source: 'household-financial-state-v1',
      observed_at: observedAt,
      as_of: observedAt,
      previous_fingerprint: 'a'.repeat(64),
      current_fingerprint: 'b'.repeat(64),
      ownership_scope: 'HOUSEHOLD',
      owner_user_id: null,
    }] : [],
    plan_diff: {
      previous_action_plan_id: 40,
      current_action_plan_id: 41,
      added_actions: [],
      removed_actions: [],
      changed_actions: status === 'CHANGED' ? [{ action_id: 'reserve' }] : [],
      unchanged_actions: [],
      financial_delta: status === 'CHANGED' ? '-100.00' : '0.00',
      investment_delta: status === 'CHANGED' ? '-200.00' : '0.00',
      hold_cash_delta: '0.00',
      priority_changes: [],
      status_change: null,
      materiality: status === 'CHANGED' ? 'HIGH' : 'NONE',
      summary: status === 'CHANGED'
        ? 'Sua capacidade de investimento diminuiu.'
        : 'Nenhuma mudança relevante foi encontrada.',
    },
    alert: status === 'CHANGED' ? {
      severity: 'IMPORTANT',
      category: 'FINANCIAL_DATA',
      title: 'Seu plano mudou',
      summary: 'A capacidade mensal mudou.',
      what_changed: ['investment_capacity'],
      why_it_matters: 'O valor autorizado para investir ficou menor.',
      recommended_action: 'Revise o novo plano antes de agir.',
      previous_reference: { action_plan_id: 40 },
      current_reference: { action_plan_id: 41 },
      dedupe_key: 'd'.repeat(64),
    } : null,
    blockers: [],
    warnings: [],
    missing_information: [],
    evidence: [],
    rule_traces: [],
    ruleset: {},
    previous_fingerprint: 'a'.repeat(64),
    current_fingerprint: 'b'.repeat(64),
    ruleset_fingerprint: 'c'.repeat(64),
    decision_fingerprint: 'd'.repeat(64),
    dedupe_key: 'e'.repeat(64),
    generated_at: observedAt,
    observed_at: observedAt,
    created_at: observedAt,
  };
}

const baseProps = {
  history: { items: [], total: 0 },
  isLoading: false,
  onRetry: vi.fn(),
  onRetryHistory: vi.fn(),
  onEvaluate: vi.fn(),
  onSelectHistory: vi.fn(),
  onShowCurrent: vi.fn(),
};

describe('ContinuousAutopilotCard', () => {
  it('renders loading and an isolated API error with retry', async () => {
    const user = userEvent.setup();
    const retry = vi.fn();
    const { rerender } = render(<ContinuousAutopilotCard {...baseProps} isLoading />);
    expect(screen.getByText('Verificando se algo importante mudou...')).toBeInTheDocument();
    rerender(
      <ContinuousAutopilotCard
        {...baseProps}
        errorMessage="Falha controlada"
        onRetry={retry}
      />,
    );
    await user.click(screen.getByRole('button', { name: 'Tentar novamente' }));
    expect(retry).toHaveBeenCalledOnce();
  });

  it('presents no-change as a successful business result', () => {
    render(<ContinuousAutopilotCard {...baseProps} decision={decision()} />);
    expect(screen.getByText('PLANO ATUALIZADO')).toBeInTheDocument();
    expect(screen.getAllByText(/Nenhuma mudança relevante foi encontrada/)).toHaveLength(2);
    expect(screen.queryByText('Executar')).not.toBeInTheDocument();
  });

  it('explains a material change and links safely to the new action plan', () => {
    render(<ContinuousAutopilotCard {...baseProps} decision={decision('CHANGED')} />);
    expect(screen.getByText('SEU PLANO MUDOU')).toBeInTheDocument();
    expect(screen.getByText('O valor autorizado para investir ficou menor.')).toBeInTheDocument();
    expect(screen.getByRole('list', { name: 'Mudanças relevantes do Autopilot' }))
      .toHaveTextContent('A capacidade financeira mensal mudou.');
    expect(screen.getByRole('link', { name: 'Ver novo plano' })).toHaveAttribute('href', '#action-plan');
  });

  it('keeps the frozen decision separate from current operational state', () => {
    const value = decision('CHANGED');
    value.operational_status = 'FAILED';
    value.last_evaluated_at = '2026-09-30T10:00:00Z';
    value.operational_warnings = [{
      code: 'LAST_EVALUATION_FAILED',
      message: 'O último plano válido foi preservado.',
      fields: [],
      rule_ids: [],
    }];
    const { rerender } = render(
      <ContinuousAutopilotCard {...baseProps} decision={value} />,
    );
    expect(screen.getByText('AVALIAÇÃO INDISPONÍVEL')).toBeInTheDocument();
    expect(screen.getByText(/Aviso operacional/)).toBeInTheDocument();

    rerender(
      <ContinuousAutopilotCard {...baseProps} decision={value} isHistorical />,
    );
    expect(screen.getByText('SEU PLANO MUDOU')).toBeInTheDocument();
    expect(screen.queryByText(/Aviso operacional/)).not.toBeInTheDocument();
  });

  it.each([
    ['REEVALUATION_REQUIRED', 'Novas informações foram registradas'],
    ['BLOCKED', 'faltam dados para atualizar o plano'],
    ['FAILED', 'último plano válido continua preservado'],
  ] as const)('renders %s without converting it into a technical error', (status, message) => {
    render(<ContinuousAutopilotCard {...baseProps} decision={decision(status)} />);
    expect(screen.getByText(new RegExp(message, 'i'))).toBeInTheDocument();
  });

  it('keeps retries idempotent in the hook contract and exposes frozen history', async () => {
    const user = userEvent.setup();
    const evaluate = vi.fn();
    const select = vi.fn();
    render(
      <ContinuousAutopilotCard
        {...baseProps}
        decision={decision('FAILED')}
        evaluationErrorMessage="Provedor indisponível"
        onEvaluate={evaluate}
        onSelectHistory={select}
        history={{
          total: 1,
          items: [{
            continuous_decision_id: 51,
            household_id: 10,
            previous_action_plan_id: 40,
            current_action_plan_id: 41,
            status: 'CHANGED',
            materiality: 'HIGH',
            alert_decision: 'IMPORTANT',
            title: 'Seu plano mudou',
            summary: 'Capacidade mensal alterada.',
            change_count: 1,
            decision_fingerprint: 'd'.repeat(64),
            observed_at: observedAt,
            generated_at: observedAt,
            created_at: observedAt,
          }],
        }}
      />,
    );
    expect(screen.getByText(/último plano válido foi preservado/i)).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Tentar novamente' }));
    expect(evaluate).toHaveBeenCalledOnce();
    await user.click(screen.getByRole('button', { name: 'Ver o que mudou' }));
    expect(select).toHaveBeenCalledWith(51);
  });
});
