import { Badge, Button, Card, ErrorState, LoadingState } from '../../../components';
import { formatCurrency } from '../../../utils/formatters';
import type {
  ActionPlan,
  ActionPlanActionType,
  ActionPlanHistory,
  ActionPlanItem,
  ActionPlanStatus,
  MoneyValue,
} from '../types/financialState.types';

const statusLabels: Record<ActionPlanStatus, string> = {
  BLOCKED: 'BLOQUEADO',
  PARTIAL: 'PARCIAL',
  READY: 'PRONTO',
  NO_ACTION_REQUIRED: 'SEM NOVA AÇÃO',
};

const actionLabels: Record<ActionPlanActionType, string> = {
  COMPLETE_INFORMATION: 'Completar informação',
  STABILIZE_CASHFLOW: 'Estabilizar fluxo de caixa',
  DEBT_PAYMENT: 'Reduzir dívida',
  EMERGENCY_RESERVE_CONTRIBUTION: 'Fortalecer reserva',
  GOAL_CONTRIBUTION: 'Avançar objetivo',
  INVESTMENT_BUY: 'Ver recomendação de compra',
  INVESTMENT_WAIT: 'Aguardar',
  INVESTMENT_AVOID: 'Evitar',
  HOLD_CASH: 'Manter em caixa',
  NO_ACTION: 'Nenhuma ação',
};

function money(value: MoneyValue) {
  return value === null || value === undefined || value === ''
    ? 'Valor não informado'
    : formatCurrency(value);
}

function statusTone(status: ActionPlanStatus): 'success' | 'warning' | 'danger' | 'neutral' {
  if (status === 'READY') return 'success';
  if (status === 'BLOCKED') return 'danger';
  if (status === 'PARTIAL') return 'warning';
  return 'neutral';
}

function actionTone(action: ActionPlanItem): 'success' | 'warning' | 'danger' | 'neutral' {
  if (action.action_type === 'INVESTMENT_BUY' || action.action_status === 'ACTIONABLE') return 'success';
  if (action.action_type === 'INVESTMENT_AVOID' || action.action_status === 'AVOID') return 'danger';
  if (action.action_status === 'WAIT' || action.action_status === 'BLOCKED') return 'warning';
  return 'neutral';
}

function ActionRow({
  action,
  orchestrationId,
  actionPlanId,
}: {
  action: ActionPlanItem;
  orchestrationId: number | null;
  actionPlanId: number | null;
}) {
  const investUrl = `/investir?modo=autopilot&household_id=${action.household_id}${
    orchestrationId === null ? '' : `&decision_id=${orchestrationId}`
  }${actionPlanId === null ? '' : `&action_plan_id=${actionPlanId}`}${
    action.asset_id === null ? '' : `&asset_id=${action.asset_id}`
  }`;
  return (
    <div role="listitem" data-testid={`action-plan-item-${action.action_type}`}>
      <strong>
        {action.priority_rank}. {action.title}{' '}
        <Badge tone={actionTone(action)}>{actionLabels[action.action_type]}</Badge>
      </strong>
      <span>
        {action.amount === null
          ? action.category === 'INFORMATION'
            ? `${money(action.amount)} · ${action.description}`
            : action.description
          : `${money(action.amount)} · ${action.description}`}
      </span>
      {action.quantity_candidate !== null && action.quantity_candidate > 0 && (
        <small>Até {action.quantity_candidate} unidade(s).</small>
      )}
      {action.price_reference !== null && (
        <small>
          Preço de referência usado na decisão: {money(action.price_reference)}
          {action.price_timestamp ? ` · ${new Date(action.price_timestamp).toLocaleString('pt-BR')}` : ''}.
          {' '}Não é garantia do preço de execução.
        </small>
      )}
      <small>Motivo: {action.reason}</small>
      {action.action_type.startsWith('INVESTMENT_') && action.action_type !== 'INVESTMENT_AVOID' && (
        <a className="vn-button vn-button--secondary" href={investUrl}>Ver oportunidade em Investir</a>
      )}
    </div>
  );
}

type ActionPlanCardProps = {
  plan?: ActionPlan;
  history?: ActionPlanHistory;
  isLoading: boolean;
  isHistoryLoading?: boolean;
  isFreezing?: boolean;
  isHistorical?: boolean;
  errorMessage?: string;
  historyErrorMessage?: string;
  freezeErrorMessage?: string;
  onRetry: () => void;
  onRetryHistory: () => void;
  onFreeze: () => void;
  onSelectHistory: (id: number) => void;
  onShowCurrent: () => void;
};

export function ActionPlanCard({
  plan,
  history,
  isLoading,
  isHistoryLoading = false,
  isFreezing = false,
  isHistorical = false,
  errorMessage,
  historyErrorMessage,
  freezeErrorMessage,
  onRetry,
  onRetryHistory,
  onFreeze,
  onSelectHistory,
  onShowCurrent,
}: ActionPlanCardProps) {
  if (isLoading) {
    return <Card title="Seu plano de ação"><LoadingState label="Organizando o que fazer agora..." /></Card>;
  }
  if (errorMessage) {
    return (
      <Card title="Seu plano de ação">
        <ErrorState
          title="Não foi possível montar seu plano"
          description={errorMessage}
          action={<Button variant="secondary" onClick={onRetry}>Tentar novamente</Button>}
        />
      </Card>
    );
  }
  if (!plan) return null;

  return (
    <Card
      title="Seu plano de ação"
      description="Ações consolidadas das decisões financeiras anteriores. Nenhuma movimentação é executada automaticamente."
      action={(
        <div className="vn-actions">
          {isHistorical
            ? <Button variant="secondary" onClick={onShowCurrent}>Voltar ao plano atual</Button>
            : (
              <Button variant="secondary" onClick={onFreeze} disabled={isFreezing}>
                {isFreezing ? 'Salvando plano de ação...' : 'Salvar plano de ação'}
              </Button>
            )}
        </div>
      )}
    >
      <div className="vn-grid vn-grid--two">
        <div>
          <span>Plano deste período</span>
          <p><Badge tone={statusTone(plan.status)}>{statusLabels[plan.status]}</Badge></p>
          <p>{plan.summary.primary_action ?? 'Nenhuma ação principal.'}</p>
        </div>
        <div>
          <span>Valores consolidados</span>
          <p>Financeiro: {money(plan.total_financial_actions)}</p>
          <p>Investimentos: {money(plan.total_investment_actions)} · caixa: {money(plan.total_hold_cash)}</p>
        </div>
      </div>

      {isHistorical && (
        <p className="vn-section-gap">
          <Badge>PLANO CONGELADO</Badge>{' '}
          Decisão de {new Date(plan.generated_at).toLocaleString('pt-BR')}. Valores e preços não foram atualizados.
        </p>
      )}

      {plan.status === 'BLOCKED' && (
        <div className="vn-section-gap">
          <h4>Ainda não é possível montar um plano seguro</h4>
          <p>Complete as informações ou resolva os bloqueios indicados abaixo.</p>
        </div>
      )}
      {plan.status === 'PARTIAL' && (
        <p className="vn-section-gap">Existe um plano parcial. Algumas ações dependem de informações adicionais.</p>
      )}
      {plan.status === 'NO_ACTION_REQUIRED' && (
        <p className="vn-section-gap">Nenhuma ação nova é necessária neste momento.</p>
      )}

      <div className="vn-section-gap">
        <h4>O que fazer agora</h4>
        <div className="vn-list" role="list" aria-label="Ações ordenadas do plano">
          {plan.actions.map((action) => (
            <ActionRow
              key={action.action_id}
              action={action}
              orchestrationId={plan.investment_orchestration_decision_id}
              actionPlanId={plan.action_plan_id}
            />
          ))}
        </div>
      </div>

      {(plan.blockers.length > 0 || plan.missing_information.length > 0) && (
        <div className="vn-grid vn-grid--two vn-section-gap">
          <div>
            <h4>Bloqueios</h4>
            {plan.blockers.length === 0
              ? <p>Nenhum bloqueio crítico.</p>
              : <ul>{plan.blockers.map((item) => <li key={`${item.code}-${item.fields.join('.')}`}>{item.message}</li>)}</ul>}
          </div>
          <div>
            <h4>Informações que podem mudar o plano</h4>
            {plan.missing_information.length === 0
              ? <p>Nenhuma informação adicional.</p>
              : <ul>{plan.missing_information.map((item) => <li key={`${item.code}-${item.fields.join('.')}`}>{item.message}</li>)}</ul>}
          </div>
        </div>
      )}

      {freezeErrorMessage && (
        <ErrorState
          title="Não foi possível salvar o plano de ação"
          description={freezeErrorMessage}
          action={<Button variant="secondary" onClick={onFreeze}>Tentar novamente</Button>}
        />
      )}

      <div className="vn-section-gap">
        <h4>Planos salvos</h4>
        {historyErrorMessage
          ? (
            <ErrorState
              title="Não foi possível carregar o histórico"
              description={historyErrorMessage}
              action={<Button variant="secondary" onClick={onRetryHistory}>Tentar novamente</Button>}
            />
          )
          : isHistoryLoading
            ? <LoadingState label="Carregando planos salvos..." />
            : history && history.items.length > 0
              ? (
                <div className="vn-list" role="list" aria-label="Histórico de planos de ação">
                  {history.items.slice(0, 5).map((item) => (
                    <div key={item.action_plan_id} role="listitem">
                      <strong>
                        {statusLabels[item.status]} · {item.primary_action ?? 'Sem ação principal'}
                      </strong>
                      <span>
                        {new Date(item.generated_at).toLocaleString('pt-BR')} · {item.action_count} ação(ões) · capital autorizado para investir: {money(item.investment_budget)} · ações: {money(item.total_financial_actions)} · investimentos: {money(item.total_investment_actions)} · caixa: {money(item.total_hold_cash)}
                      </span>
                      {item.action_titles.length > 0 && (
                        <small>Principais ações: {item.action_titles.join(' · ')}</small>
                      )}
                      <Button variant="secondary" onClick={() => onSelectHistory(item.action_plan_id)}>Ver plano congelado</Button>
                    </div>
                  ))}
                </div>
              )
              : <p>Nenhum plano foi congelado ainda.</p>}
      </div>
    </Card>
  );
}
