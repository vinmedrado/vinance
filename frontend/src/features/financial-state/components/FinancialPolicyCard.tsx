import { Badge, Button, Card, ErrorState, LoadingState } from '../../../components';
import type {
  FinancialPolicy,
  FinancialPolicyEvidence,
  FinancialPolicyHistory,
  FinancialPolicyState,
  InvestmentReadiness,
} from '../types/financialState.types';


const stateLabels: Record<FinancialPolicyState, string> = {
  DATA_BLOCKED: 'Completar dados financeiros críticos',
  CASHFLOW_RECOVERY: 'Estabilizar o fluxo de caixa',
  DEBT_PRIORITY: 'Reduzir a pressão das dívidas',
  EMERGENCY_RESERVE_PRIORITY: 'Fortalecer a reserva de emergência',
  GOAL_PRIORITY: 'Financiar o objetivo prioritário',
  BALANCED_BUILD: 'Avançar com construção equilibrada',
  INVESTMENT_READY: 'Investir somente o capital excedente',
};

const readinessLabels: Record<InvestmentReadiness, string> = {
  BLOCKED: 'BLOQUEADO',
  LIMITED: 'LIMITADO',
  READY: 'PRONTO',
};

function readinessTone(readiness: InvestmentReadiness): 'success' | 'warning' | 'danger' {
  if (readiness === 'READY') return 'success';
  if (readiness === 'BLOCKED') return 'danger';
  return 'warning';
}

function displayEvidence(evidence: FinancialPolicyEvidence) {
  if (evidence.value === null || evidence.value === undefined || evidence.value === '') {
    return 'Não informado';
  }
  if (evidence.unit === 'BRL' && !Number.isNaN(Number(evidence.value))) {
    return new Intl.NumberFormat('pt-BR', {
      style: 'currency',
      currency: 'BRL',
    }).format(Number(evidence.value));
  }
  if (evidence.unit === 'PERCENT' && !Number.isNaN(Number(evidence.value))) {
    return `${Number(evidence.value).toLocaleString('pt-BR')}%`;
  }
  if (evidence.unit === 'MONTHS' && !Number.isNaN(Number(evidence.value))) {
    return `${Number(evidence.value).toLocaleString('pt-BR')} meses`;
  }
  if (Array.isArray(evidence.value)) {
    return evidence.value.length > 0 ? evidence.value.join(', ') : 'Nenhum';
  }
  return String(evidence.value);
}

type FinancialPolicyCardProps = {
  policy?: FinancialPolicy;
  history?: FinancialPolicyHistory;
  isLoading: boolean;
  isHistoryLoading?: boolean;
  isFreezing?: boolean;
  errorMessage?: string;
  historyErrorMessage?: string;
  freezeErrorMessage?: string;
  onRetry: () => void;
  onRetryHistory: () => void;
  onFreeze: () => void;
};

export function FinancialPolicyCard({
  policy,
  history,
  isLoading,
  isHistoryLoading = false,
  isFreezing = false,
  errorMessage,
  historyErrorMessage,
  freezeErrorMessage,
  onRetry,
  onRetryHistory,
  onFreeze,
}: FinancialPolicyCardProps) {
  if (isLoading) {
    return (
      <Card title="Sua prioridade agora">
        <LoadingState label="Calculando uma política segura com os dados conhecidos..." />
      </Card>
    );
  }

  if (errorMessage) {
    return (
      <Card title="Sua prioridade agora">
        <ErrorState
          title="Não foi possível calcular suas prioridades"
          description={errorMessage}
          action={<Button variant="secondary" onClick={onRetry}>Tentar novamente</Button>}
        />
      </Card>
    );
  }

  if (!policy) return null;

  const active = policy.priority_stack.find((priority) => priority.status === 'ACTIVE')
    ?? policy.priority_stack[0];
  const next = policy.priority_stack.filter(
    (priority) => priority.code !== active?.code
      && (priority.status === 'NEXT' || priority.status === 'CONDITIONAL'),
  );
  const explanation = policy.explanations.find(
    (item) => item.code === 'PRIMARY_POLICY_DECISION',
  ) ?? policy.explanations[0];
  const evidenceByCode = new Map(policy.evidence.map((item) => [item.code, item]));
  const visibleEvidence = (explanation?.evidence_refs ?? active?.evidence_refs ?? [])
    .map((code) => evidenceByCode.get(code))
    .filter((item): item is FinancialPolicyEvidence => Boolean(item));

  return (
    <Card
      title="Sua prioridade agora"
      description="Uma ordem dinâmica baseada na situação real conhecida. Nenhum ativo, mercado ou valor de compra é escolhido aqui."
      action={(
        <Button variant="secondary" onClick={onFreeze} disabled={isFreezing}>
          {isFreezing ? 'Salvando decisão...' : 'Salvar decisão'}
        </Button>
      )}
    >
      <div>
        <span>Prioridade principal</span>
        <h3>{active?.title ?? stateLabels[policy.policy_state]}</h3>
        <p>{policy.summary}</p>
      </div>

      <div className="vn-section-gap">
        <h4>Por quê?</h4>
        <p>{explanation?.reason ?? active?.explanation}</p>
        {visibleEvidence.length > 0 && (
          <ul>
            {visibleEvidence.map((item) => (
              <li key={item.code}>{item.label}: <strong>{displayEvidence(item)}</strong></li>
            ))}
          </ul>
        )}
      </div>

      <div className="vn-grid vn-grid--two vn-section-gap">
        <div>
          <h4>Depois disso</h4>
          {next.length === 0
            ? <p>Nenhuma prioridade intermediária adicional nos dados conhecidos.</p>
            : (
              <ol>
                {next.map((priority) => (
                  <li key={priority.code}>
                    <strong>{priority.title}</strong>
                    <br />
                    <span>{priority.explanation}</span>
                  </li>
                ))}
              </ol>
            )}
        </div>
        <div>
          <h4>Investir agora</h4>
          <Badge tone={readinessTone(policy.investment_readiness)}>
            {readinessLabels[policy.investment_readiness]}
          </Badge>
          <p>{policy.explanations.find(
            (item) => item.code === 'INVESTMENT_READINESS_DECISION',
          )?.reason}</p>
        </div>
      </div>

      {policy.missing_information.length > 0 && (
        <div className="vn-section-gap">
          <h4>O que falta informar</h4>
          <ul>
            {policy.missing_information.map((item) => (
              <li key={item.code}>{item.message}</li>
            ))}
          </ul>
        </div>
      )}

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

      {policy.member_policy_views.length > 1 && (
        <div className="vn-section-gap">
          <h4>Visões individuais</h4>
          <div className="vn-list" role="list" aria-label="Prioridades pessoais dos membros">
            {policy.member_policy_views.map((member) => (
              <div key={member.user_id} role="listitem">
                <strong>{member.full_name ?? `Membro ${member.user_id}`}</strong>
                <span>{stateLabels[member.policy_state]}. {member.explanation}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {freezeErrorMessage && (
        <ErrorState
          title="Não foi possível salvar a decisão"
          description={freezeErrorMessage}
          action={<Button variant="secondary" onClick={onFreeze}>Tentar novamente</Button>}
        />
      )}

      <div className="vn-section-gap">
        <h4>Decisões salvas</h4>
        {historyErrorMessage
          ? (
            <ErrorState
              title="Não foi possível carregar as decisões salvas"
              description={historyErrorMessage}
              action={<Button variant="secondary" onClick={onRetryHistory}>Tentar novamente</Button>}
            />
          )
          : isHistoryLoading
          ? <LoadingState label="Carregando histórico de decisões..." />
          : history && history.items.length > 0
            ? (
              <div className="vn-list" role="list" aria-label="Histórico de políticas financeiras">
                {history.items.slice(0, 5).map((item) => (
                  <div key={item.policy_id} role="listitem">
                    <strong>{stateLabels[item.policy_state]}</strong>
                    <span>
                      {new Date(item.generated_at).toLocaleString('pt-BR')} · investir agora: {' '}
                      {readinessLabels[item.investment_readiness]}
                    </span>
                  </div>
                ))}
              </div>
            )
            : <p>Nenhuma decisão foi congelada ainda.</p>}
      </div>
    </Card>
  );
}
