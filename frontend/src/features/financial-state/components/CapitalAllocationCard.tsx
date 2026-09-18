import { Badge, Button, Card, ErrorState, LoadingState } from '../../../components';
import { formatCurrency } from '../../../utils/formatters';
import type {
  CapitalAllocation,
  CapitalAllocationHistory,
  CapitalAllocationItem,
  CapitalAllocationStatus,
  MoneyValue,
} from '../types/financialState.types';


const statusLabels: Record<CapitalAllocationStatus, string> = {
  BLOCKED: 'BLOQUEADO',
  CONSTRAINED: 'RESTRITO',
  ACTIVE: 'ATIVO',
  SURPLUS: 'COM CAPITAL ELEGÍVEL',
};

const priorityLabels: Record<string, string> = {
  COMPLETE_CRITICAL_DATA: 'Completar informações críticas',
  COMPLETE_READINESS_DATA: 'Completar informações de prontidão',
  STABILIZE_CASH_FLOW: 'Estabilizar o fluxo de caixa',
  REDUCE_DEBT_BURDEN: 'Reduzir dívidas prioritárias',
  BUILD_EMERGENCY_RESERVE: 'Reserva de emergência',
  FUND_PRIORITY_GOAL: 'Objetivo prioritário',
  INVEST_SURPLUS_CAPITAL: 'Disponível para investir',
};

function isKnown(value: MoneyValue): value is string | number {
  return value !== null && value !== undefined && value !== '';
}

function money(value: MoneyValue) {
  return isKnown(value) ? formatCurrency(value) : 'Não calculável';
}

function statusTone(status: CapitalAllocationStatus): 'success' | 'warning' | 'danger' {
  if (status === 'SURPLUS') return 'success';
  if (status === 'BLOCKED') return 'danger';
  return 'warning';
}

function itemTitle(item: CapitalAllocationItem) {
  return item.target_name || priorityLabels[item.priority_code] || 'Prioridade financeira';
}

type CapitalAllocationCardProps = {
  allocation?: CapitalAllocation;
  history?: CapitalAllocationHistory;
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

export function CapitalAllocationCard({
  allocation,
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
}: CapitalAllocationCardProps) {
  if (isLoading) {
    return (
      <Card title="Plano deste período">
        <LoadingState label="Distribuindo apenas o capital comprovadamente disponível..." />
      </Card>
    );
  }

  if (errorMessage) {
    return (
      <Card title="Plano deste período">
        <ErrorState
          title="Não foi possível calcular o plano"
          description={errorMessage}
          action={<Button variant="secondary" onClick={onRetry}>Tentar novamente</Button>}
        />
      </Card>
    );
  }

  if (!allocation) return null;

  const visibleAllocations = allocation.allocations.filter(
    (item) => item.bucket_type !== 'INFORMATIONAL',
  );

  return (
    <Card
      title="Plano deste período"
      description="Valores mensais derivados da sua situação e das prioridades atuais. Nenhum ativo ou compra é escolhido aqui."
      action={(
        <Button variant="secondary" onClick={onFreeze} disabled={isFreezing}>
          {isFreezing ? 'Salvando plano...' : 'Salvar plano'}
        </Button>
      )}
    >
      <div className="vn-grid vn-grid--two">
        <div>
          <span>Capital disponível no período</span>
          <h3>{money(allocation.allocatable_capital)}</h3>
          <p>
            {allocation.allocatable_capital === null
              ? 'Os dados atuais não permitem afirmar quanto pode ser distribuído.'
              : 'Somente capacidade mensal conhecida; patrimônio existente não foi tratado como caixa.'}
          </p>
        </div>
        <div>
          <span>Status do plano</span>
          <p><Badge tone={statusTone(allocation.allocation_status)}>{statusLabels[allocation.allocation_status]}</Badge></p>
          <p>Período: mensal · moeda: {allocation.currency}</p>
        </div>
      </div>

      <div className="vn-section-gap">
        <h4>Destino do capital</h4>
        {visibleAllocations.length === 0
          ? <p>Nenhum valor pode ser destinado com segurança neste período.</p>
          : (
            <div className="vn-list" role="list" aria-label="Plano de capital do período">
              {visibleAllocations.map((item, index) => (
                <div
                  key={`${item.priority_code}-${String(item.target_id ?? 'general')}-${index}`}
                  role="listitem"
                >
                  <strong>{itemTitle(item)}</strong>
                  <span>
                    {money(item.allocated_amount)}
                    {item.ownership_scope ? ` · ${item.ownership_scope === 'PERSONAL' ? 'pessoal' : 'household'}` : ''}
                    {item.remaining_need !== null ? ` · ainda falta ${money(item.remaining_need)}` : ''}
                  </span>
                  <small>{item.reason}</small>
                </div>
              ))}
            </div>
          )}
      </div>

      <div className="vn-grid vn-grid--two vn-section-gap">
        <div>
          <h4>Disponível para investir</h4>
          <p><strong>{money(allocation.investment_bucket_amount)}</strong></p>
          <p>Este é apenas o limite elegível para a próxima fase; não existe seleção de produto ou ativo específico.</p>
        </div>
        <div>
          <h4>Não alocado</h4>
          <p><strong>{money(allocation.remaining_capital)}</strong></p>
          <p>Capital bloqueado ou sem destino seguro permanece fora de qualquer investimento.</p>
        </div>
      </div>

      {(allocation.blockers.length > 0 || allocation.missing_information.length > 0) && (
        <div className="vn-grid vn-grid--two vn-section-gap">
          <div>
            <h4>O que impede avançar</h4>
            {allocation.blockers.length > 0
              ? <ul>{allocation.blockers.map((item) => <li key={`${item.code}-${item.fields.join('.')}`}>{item.message}</li>)}</ul>
              : <p>Nenhum bloqueio nos dados conhecidos.</p>}
          </div>
          <div>
            <h4>O que falta informar</h4>
            {allocation.missing_information.length > 0
              ? <ul>{allocation.missing_information.map((item) => <li key={`${item.code}-${item.fields.join('.')}`}>{item.message}</li>)}</ul>
              : <p>Nenhuma informação adicional necessária.</p>}
          </div>
        </div>
      )}

      {allocation.warnings.length > 0 && (
        <div className="vn-section-gap">
          <h4>Pontos de atenção</h4>
          <ul>{allocation.warnings.map((item) => <li key={`${item.code}-${item.fields.join('.')}`}>{item.message}</li>)}</ul>
        </div>
      )}

      {allocation.member_impacts.length > 1 && (
        <div className="vn-section-gap">
          <h4>Impacto por membro</h4>
          <div className="vn-list" role="list" aria-label="Impacto do plano por membro">
            {allocation.member_impacts.map((member) => (
              <div key={member.user_id} role="listitem">
                <strong>{member.full_name ?? `Membro ${member.user_id}`}</strong>
                <span>Prioridades pessoais: {money(member.allocated_to_personal_priorities)}</span>
                <small>{member.explanation}</small>
              </div>
            ))}
          </div>
        </div>
      )}

      {freezeErrorMessage && (
        <ErrorState
          title="Não foi possível salvar o plano"
          description={freezeErrorMessage}
          action={<Button variant="secondary" onClick={onFreeze}>Tentar novamente</Button>}
        />
      )}

      <div className="vn-section-gap">
        <h4>Planos salvos</h4>
        {historyErrorMessage
          ? (
            <ErrorState
              title="Não foi possível carregar os planos salvos"
              description={historyErrorMessage}
              action={<Button variant="secondary" onClick={onRetryHistory}>Tentar novamente</Button>}
            />
          )
          : isHistoryLoading
          ? <LoadingState label="Carregando histórico de planos..." />
          : history && history.items.length > 0
            ? (
              <div className="vn-list" role="list" aria-label="Histórico de planos de capital">
                {history.items.slice(0, 5).map((item) => (
                  <div key={item.allocation_id} role="listitem">
                    <strong>{statusLabels[item.allocation_status]}</strong>
                    <span>
                      {new Date(item.generated_at).toLocaleString('pt-BR')} · disponível: {' '}
                      {money(item.allocatable_capital)} · para investir: {' '}
                      {money(item.investment_bucket_amount)}
                    </span>
                  </div>
                ))}
              </div>
            )
            : <p>Nenhum plano foi congelado ainda.</p>}
      </div>
    </Card>
  );
}
