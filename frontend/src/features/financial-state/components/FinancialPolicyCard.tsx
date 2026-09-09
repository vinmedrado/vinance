import { Badge, Button, Card, ErrorState, LoadingState } from '../../../components';
import type {
  FinancialPolicy,
  FinancialPolicyState,
  InvestmentReadiness,
} from '../types/financialState.types';


const stateLabels: Record<FinancialPolicyState, string> = {
  DATA_BLOCKED: 'Dados críticos pendentes',
  CASHFLOW_RECOVERY: 'Recuperação do fluxo de caixa',
  DEBT_PRIORITY: 'Dívidas em prioridade',
  EMERGENCY_RESERVE_PRIORITY: 'Reserva em prioridade',
  GOAL_PRIORITY: 'Objetivo em prioridade',
  BALANCED_BUILD: 'Construção equilibrada',
  INVESTMENT_READY: 'Situação pronta para aportes',
};

const readinessLabels: Record<InvestmentReadiness, string> = {
  BLOCKED: 'Novos aportes bloqueados',
  LIMITED: 'Novos aportes limitados',
  READY: 'Capital excedente disponível',
};

const priorityStatusLabels = {
  ACTIVE: 'Agora',
  NEXT: 'Depois',
  CONDITIONAL: 'Condicional',
  BLOCKED: 'Bloqueada',
} as const;

function readinessTone(readiness: InvestmentReadiness): 'success' | 'warning' | 'danger' {
  if (readiness === 'READY') return 'success';
  if (readiness === 'BLOCKED') return 'danger';
  return 'warning';
}

function activePriorityTone(
  policyState: FinancialPolicyState,
): 'success' | 'warning' | 'danger' {
  if (policyState === 'INVESTMENT_READY') return 'success';
  if (policyState === 'DATA_BLOCKED' || policyState === 'CASHFLOW_RECOVERY') return 'danger';
  return 'warning';
}

type FinancialPolicyCardProps = {
  policy?: FinancialPolicy;
  isLoading: boolean;
  errorMessage?: string;
  onRetry: () => void;
};

export function FinancialPolicyCard({
  policy,
  isLoading,
  errorMessage,
  onRetry,
}: FinancialPolicyCardProps) {
  if (isLoading) {
    return (
      <Card title="Prioridades financeiras agora">
        <LoadingState label="Calculando uma política segura com os dados conhecidos..." />
      </Card>
    );
  }

  if (errorMessage) {
    return (
      <Card title="Prioridades financeiras agora">
        <ErrorState
          title="Não foi possível calcular suas prioridades"
          description={errorMessage}
          action={<Button variant="secondary" onClick={onRetry}>Tentar novamente</Button>}
        />
      </Card>
    );
  }

  if (!policy) return null;

  return (
    <Card
      title="Prioridades financeiras agora"
      description="Uma ordem dinâmica baseada na situação atual. Ela não escolhe ativos, mercados ou valores de compra."
      action={(
        <Badge tone={readinessTone(policy.investment_readiness)}>
          {readinessLabels[policy.investment_readiness]}
        </Badge>
      )}
    >
      <p><strong>{stateLabels[policy.policy_state]}.</strong> {policy.summary}</p>

      <div className="vn-list vn-section-gap" role="list" aria-label="Ordem de prioridades financeiras">
        {policy.priority_stack.map((priority) => (
          <div key={priority.code} role="listitem">
            <strong>
              {priority.rank}. {priority.title}
              <Badge tone={priority.status === 'ACTIVE'
                ? activePriorityTone(policy.policy_state)
                : priority.status === 'BLOCKED'
                  ? 'danger'
                  : 'neutral'}>
                {priorityStatusLabels[priority.status]}
              </Badge>
            </strong>
            <span>{priority.explanation}</span>
          </div>
        ))}
      </div>

      {(policy.blockers.length > 0 || policy.warnings.length > 0) && (
        <div className="vn-grid vn-grid--two vn-section-gap">
          <div>
            <h4>O que impede avançar</h4>
            {policy.blockers.length === 0
              ? <p>Nenhum bloqueio identificado nos dados conhecidos.</p>
              : <ul>{policy.blockers.map((item) => <li key={item.code}>{item.message}</li>)}</ul>}
          </div>
          <div>
            <h4>Pontos de atenção</h4>
            {policy.warnings.length === 0
              ? <p>Nenhum alerta adicional.</p>
              : <ul>{policy.warnings.map((item) => <li key={item.code}>{item.message}</li>)}</ul>}
          </div>
        </div>
      )}

      {policy.limitations.length > 0 && (
        <div className="vn-section-gap">
          <h4>Limites desta leitura</h4>
          <ul>{policy.limitations.map((item) => <li key={item.code}>{item.message}</li>)}</ul>
        </div>
      )}
    </Card>
  );
}
