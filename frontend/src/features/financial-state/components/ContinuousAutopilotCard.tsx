import { Badge, Button, Card, ErrorState, LoadingState } from '../../../components';
import type {
  ContinuousAlertDecision,
  ContinuousAutopilot,
  ContinuousAutopilotHistory,
  ContinuousAutopilotStatus,
  ContinuousMateriality,
  MoneyValue,
} from '../types/financialState.types';

const statusLabels: Record<ContinuousAutopilotStatus, string> = {
  UP_TO_DATE: 'PLANO ATUALIZADO',
  REEVALUATION_REQUIRED: 'REAVALIAÇÃO NECESSÁRIA',
  EVALUATING: 'AVALIANDO MUDANÇAS',
  CHANGED: 'SEU PLANO MUDOU',
  UNCHANGED: 'PLANO ATUALIZADO',
  BLOCKED: 'PRECISAMOS DE INFORMAÇÕES',
  FAILED: 'AVALIAÇÃO INDISPONÍVEL',
};

const alertLabels: Record<ContinuousAlertDecision, string> = {
  NO_ALERT: 'Sem alerta',
  INFORMATIONAL: 'Informativo',
  ACTION_RECOMMENDED: 'Ação recomendada',
  IMPORTANT: 'Importante',
  CRITICAL: 'Crítico',
};

const materialityLabels: Record<ContinuousMateriality, string> = {
  NONE: 'Sem mudança',
  LOW: 'Baixa',
  MEDIUM: 'Média',
  HIGH: 'Alta',
  CRITICAL: 'Crítica',
};

function statusTone(
  status: ContinuousAutopilotStatus,
): 'success' | 'warning' | 'danger' | 'neutral' {
  if (status === 'UP_TO_DATE' || status === 'UNCHANGED') return 'success';
  if (status === 'FAILED' || status === 'BLOCKED') return 'danger';
  if (status === 'CHANGED' || status === 'REEVALUATION_REQUIRED') return 'warning';
  return 'neutral';
}

function materialityTone(
  materiality: ContinuousMateriality,
): 'success' | 'warning' | 'danger' | 'neutral' {
  if (materiality === 'CRITICAL') return 'danger';
  if (materiality === 'HIGH' || materiality === 'MEDIUM') return 'warning';
  if (materiality === 'NONE') return 'success';
  return 'neutral';
}

function delta(value: MoneyValue) {
  if (value === null || value === undefined || value === '') return 'não calculado';
  const number = Number(value);
  const prefix = number > 0 ? '+' : '';
  return `${prefix}${number.toLocaleString('pt-BR', {
    style: 'currency',
    currency: 'BRL',
  })}`;
}

function currentMessage(decision: ContinuousAutopilot, status: ContinuousAutopilotStatus) {
  if (status === 'UP_TO_DATE' || status === 'UNCHANGED') {
    return 'Nenhuma mudança relevante foi encontrada desde a última avaliação.';
  }
  if (status === 'REEVALUATION_REQUIRED') {
    return 'Novas informações foram registradas e precisam ser avaliadas com segurança.';
  }
  if (status === 'EVALUATING') return 'O VinanceOS está verificando a cadeia de decisões.';
  if (status === 'BLOCKED') {
    return 'Uma mudança foi detectada, mas faltam dados para atualizar o plano com segurança.';
  }
  if (status === 'FAILED') {
    return 'A última avaliação não terminou. Seu último plano válido continua preservado.';
  }
  return decision.alert?.summary || decision.plan_diff.summary;
}

type ContinuousAutopilotCardProps = {
  decision?: ContinuousAutopilot;
  history?: ContinuousAutopilotHistory;
  isLoading: boolean;
  isHistoryLoading?: boolean;
  isEvaluating?: boolean;
  isHistorical?: boolean;
  errorMessage?: string;
  historyErrorMessage?: string;
  evaluationErrorMessage?: string;
  onRetry: () => void;
  onRetryHistory: () => void;
  onEvaluate: () => void;
  onSelectHistory: (id: number) => void;
  onShowCurrent: () => void;
};

export function ContinuousAutopilotCard({
  decision,
  history,
  isLoading,
  isHistoryLoading = false,
  isEvaluating = false,
  isHistorical = false,
  errorMessage,
  historyErrorMessage,
  evaluationErrorMessage,
  onRetry,
  onRetryHistory,
  onEvaluate,
  onSelectHistory,
  onShowCurrent,
}: ContinuousAutopilotCardProps) {
  if (isLoading) {
    return <Card title="Seu Autopilot"><LoadingState label="Verificando se algo importante mudou..." /></Card>;
  }
  if (errorMessage) {
    return (
      <Card title="Seu Autopilot">
        <ErrorState
          title="Não foi possível consultar o Autopilot"
          description={errorMessage}
          action={<Button variant="secondary" onClick={onRetry}>Tentar novamente</Button>}
        />
      </Card>
    );
  }
  if (!decision) return null;

  const displayedStatus = !isHistorical && decision.operational_status
    ? decision.operational_status
    : decision.status;
  const requiresEvaluation = displayedStatus === 'REEVALUATION_REQUIRED'
    || displayedStatus === 'FAILED'
    || decision.continuous_decision_id === null;
  const showPlanCta = decision.current_action_plan_id !== null
    && (decision.status === 'CHANGED' || decision.alert_decision !== 'NO_ALERT');

  return (
    <Card
      title="Seu Autopilot"
      description="Monitora mudanças relevantes sem executar movimentações financeiras automaticamente."
      action={isHistorical
        ? <Button variant="secondary" onClick={onShowCurrent}>Voltar ao status atual</Button>
        : (
          <Button variant="secondary" onClick={onEvaluate} disabled={isEvaluating}>
            {isEvaluating ? 'Avaliando...' : requiresEvaluation ? 'Avaliar agora' : 'Verificar mudanças'}
          </Button>
        )}
    >
      <div className="vn-grid vn-grid--two">
        <div>
          <p><Badge tone={statusTone(displayedStatus)}>{statusLabels[displayedStatus]}</Badge></p>
          <p>{currentMessage(decision, displayedStatus)}</p>
          <small>
            Última avaliação: {new Date(
              !isHistorical && decision.last_evaluated_at
                ? decision.last_evaluated_at
                : decision.observed_at,
            ).toLocaleString('pt-BR')}.
          </small>
        </div>
        <div>
          <p>
            <Badge tone={materialityTone(decision.materiality)}>
              {materialityLabels[decision.materiality]}
            </Badge>{' '}
            <Badge>{alertLabels[decision.alert_decision]}</Badge>
          </p>
          <p>{decision.plan_diff.summary}</p>
          {showPlanCta && <a className="vn-button vn-button--secondary" href="#action-plan">Ver novo plano</a>}
        </div>
      </div>

      {isHistorical && (
        <p className="vn-section-gap">
          <Badge>AVALIAÇÃO CONGELADA</Badge>{' '}
          Esta visão usa apenas os dados e decisões preservados naquele momento.
        </p>
      )}

      {decision.alert && (
        <div className="vn-section-gap">
          <h4>{decision.alert.title}</h4>
          <p>{decision.alert.why_it_matters}</p>
          <p><strong>Ação recomendada:</strong> {decision.alert.recommended_action}</p>
        </div>
      )}

      {decision.detected_changes.length > 0 && (
        <div className="vn-section-gap">
          <h4>O que mudou</h4>
          <div className="vn-list" role="list" aria-label="Mudanças relevantes do Autopilot">
            {decision.detected_changes.map((change) => (
              <div key={change.change_id} role="listitem">
                <strong>{change.reason}</strong>
                <span>{change.category.replace(/_/g, ' ')} · {change.materiality}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {(Number(decision.plan_diff.financial_delta) !== 0
        || Number(decision.plan_diff.investment_delta) !== 0
        || Number(decision.plan_diff.hold_cash_delta) !== 0) && (
        <div className="vn-grid vn-grid--two vn-section-gap">
          <div>
            <strong>Mudanças no plano</strong>
            <p>Financeiro: {delta(decision.plan_diff.financial_delta)}</p>
            <p>Investimentos: {delta(decision.plan_diff.investment_delta)}</p>
          </div>
          <div>
            <strong>Caixa preservado</strong>
            <p>{delta(decision.plan_diff.hold_cash_delta)}</p>
            <p>{decision.plan_diff.changed_actions.length} ação(ões) alterada(s).</p>
          </div>
        </div>
      )}

      {(decision.blockers.length > 0 || decision.missing_information.length > 0) && (
        <div className="vn-grid vn-grid--two vn-section-gap">
          <div>
            <h4>Bloqueios</h4>
            {decision.blockers.length === 0
              ? <p>Nenhum bloqueio crítico.</p>
              : <ul>{decision.blockers.map((item) => <li key={item.code}>{item.message}</li>)}</ul>}
          </div>
          <div>
            <h4>Informações necessárias</h4>
            {decision.missing_information.length === 0
              ? <p>Nenhuma informação adicional.</p>
              : <ul>{decision.missing_information.map((item) => <li key={item.code}>{item.message}</li>)}</ul>}
          </div>
        </div>
      )}

      {evaluationErrorMessage && (
        <ErrorState
          title="Não foi possível concluir a avaliação"
          description={`${evaluationErrorMessage} Seu último plano válido foi preservado.`}
          action={<Button variant="secondary" onClick={onEvaluate}>Tentar novamente</Button>}
        />
      )}

      {!isHistorical && decision.operational_warnings && decision.operational_warnings.length > 0 && (
        <div className="vn-section-gap">
          {decision.operational_warnings.map((item) => (
            <p key={item.code}><strong>Aviso operacional:</strong> {item.message}</p>
          ))}
        </div>
      )}

      <div className="vn-section-gap">
        <h4>Linha do tempo</h4>
        {historyErrorMessage
          ? (
            <ErrorState
              title="Não foi possível carregar a linha do tempo"
              description={historyErrorMessage}
              action={<Button variant="secondary" onClick={onRetryHistory}>Tentar novamente</Button>}
            />
          )
          : isHistoryLoading
            ? <LoadingState label="Carregando avaliações anteriores..." />
            : history && history.items.length > 0
              ? (
                <div className="vn-list" role="list" aria-label="Histórico do Continuous Autopilot">
                  {history.items.slice(0, 5).map((item) => (
                    <div key={item.continuous_decision_id} role="listitem">
                      <strong>{item.title}</strong>
                      <span>{new Date(item.observed_at).toLocaleString('pt-BR')} · {item.summary}</span>
                      <small>{item.change_count} mudança(s) relevante(s) · {item.materiality}</small>
                      <Button
                        variant="secondary"
                        onClick={() => onSelectHistory(item.continuous_decision_id)}
                      >
                        Ver o que mudou
                      </Button>
                    </div>
                  ))}
                </div>
              )
              : <p>Nenhuma avaliação histórica foi registrada ainda.</p>}
      </div>
    </Card>
  );
}
