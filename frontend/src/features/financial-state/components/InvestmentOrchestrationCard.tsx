import { Badge, Button, Card, ErrorState, LoadingState } from '../../../components';
import { formatCurrency } from '../../../utils/formatters';
import type {
  InvestmentOrchestration,
  InvestmentOrchestrationHistory,
  InvestmentOrchestrationStatus,
  MoneyValue,
  RankedInvestmentOpportunity,
} from '../types/financialState.types';

const statusLabels: Record<InvestmentOrchestrationStatus, string> = {
  BLOCKED: 'BLOQUEADO',
  LIMITED: 'LIMITADO',
  ACTIVE: 'ATIVO',
  NO_SUITABLE_OPPORTUNITY: 'AGUARDAR',
};

const marketLabels: Record<string, string> = {
  ACOES: 'Ações',
  FII: 'FIIs',
  ETF: 'ETFs',
  BDR: 'BDRs',
  FIXED_INCOME: 'Renda fixa',
  CRYPTO: 'Criptoativos',
};

const actionLabels: Record<RankedInvestmentOpportunity['action'], string> = {
  BUY: 'Comprar',
  WAIT: 'Aguardar',
  AVOID: 'Evitar',
  NO_RECOMMENDATION: 'Sem recomendação',
};

function isKnown(value: MoneyValue): value is string | number {
  return value !== null && value !== undefined && value !== '';
}

function money(value: MoneyValue) {
  return isKnown(value) ? formatCurrency(value) : 'Não informado';
}

function statusTone(status: InvestmentOrchestrationStatus): 'success' | 'warning' | 'danger' {
  if (status === 'ACTIVE') return 'success';
  if (status === 'BLOCKED') return 'danger';
  return 'warning';
}

function actionTone(action: RankedInvestmentOpportunity['action']): 'success' | 'warning' | 'danger' | 'neutral' {
  if (action === 'BUY') return 'success';
  if (action === 'AVOID') return 'danger';
  if (action === 'WAIT') return 'warning';
  return 'neutral';
}

type InvestmentOrchestrationCardProps = {
  orchestration?: InvestmentOrchestration;
  history?: InvestmentOrchestrationHistory;
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

export function InvestmentOrchestrationCard({
  orchestration,
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
}: InvestmentOrchestrationCardProps) {
  if (isLoading) {
    return (
      <Card title="Como investir este valor">
        <LoadingState label="Validando perfil, mercado e oportunidades atuais..." />
      </Card>
    );
  }

  if (errorMessage) {
    return (
      <Card title="Como investir este valor">
        <ErrorState
          title="Não foi possível montar a estratégia"
          description={errorMessage}
          action={<Button variant="secondary" onClick={onRetry}>Tentar novamente</Button>}
        />
      </Card>
    );
  }

  if (!orchestration) return null;

  const investUrl = `/investir?modo=autopilot&household_id=${orchestration.household_id}${
    orchestration.orchestration_id === null
      ? ''
      : `&decision_id=${orchestration.orchestration_id}`
  }`;
  const opportunities = orchestration.ranked_opportunities.slice(0, 5);

  return (
    <Card
      title="Como investir este valor"
      description="Estratégia derivada do capital liberado no plano. Nenhuma compra ou ordem é executada."
      action={(
        <div className="vn-actions">
          <Button variant="secondary" onClick={onFreeze} disabled={isFreezing}>
            {isFreezing ? 'Salvando estratégia...' : 'Salvar estratégia'}
          </Button>
          <a className="vn-button vn-button--secondary" href={investUrl}>Abrir em Investir</a>
        </div>
      )}
    >
      <div className="vn-grid vn-grid--two">
        <div>
          <span>Disponível para investir</span>
          <h3>{money(orchestration.investment_budget)}</h3>
          <p>Somente o investment bucket autorizado pelo plano deste período.</p>
        </div>
        <div>
          <span>Estratégia atual</span>
          <p><Badge tone={statusTone(orchestration.status)}>{statusLabels[orchestration.status]}</Badge></p>
          <p>Sugerido: {money(orchestration.suggested_capital)} · em caixa: {money(orchestration.remaining_investment_cash)}</p>
        </div>
      </div>

      <div className="vn-section-gap">
        <h4>Direção por classe</h4>
        {orchestration.class_allocations.length === 0
          ? <p>Nenhuma classe recebeu capital neste momento.</p>
          : (
            <div className="vn-list" role="list" aria-label="Estratégia por classe de ativos">
              {orchestration.class_allocations.map((item) => (
                <div key={item.market} role="listitem">
                  <strong>{marketLabels[item.market] ?? item.market}</strong>
                  <span>{money(item.allocated_amount)} · compromisso sugerido: {money(item.suggested_capital)}</span>
                  <small>Caixa preservado na classe: {money(item.remaining_cash)}</small>
                </div>
              ))}
            </div>
          )}
      </div>

      <div className="vn-section-gap">
        <h4>Principais oportunidades</h4>
        {opportunities.length === 0
          ? (
            <p>
              {orchestration.status === 'NO_SUITABLE_OPPORTUNITY'
                ? 'Existe capital autorizado, mas nenhuma oportunidade passou pelos critérios atuais. O valor permanece em caixa.'
                : 'Nenhuma oportunidade financiável está disponível com os dados atuais.'}
            </p>
          )
          : (
            <div className="vn-list" role="list" aria-label="Oportunidades avaliadas pelo Autopilot">
              {opportunities.map((item) => (
                <div key={`${item.market}-${item.symbol}`} role="listitem">
                  <strong>
                    {item.symbol}{' '}
                    <Badge tone={actionTone(item.action)}>{actionLabels[item.action]}</Badge>
                  </strong>
                  <span>
                    {marketLabels[item.market] ?? item.market} · capital: {money(item.capital_committed)}
                    {item.quantity_suggested > 0 ? ` · ${item.quantity_suggested} unidade(s)` : ''}
                  </span>
                  <small>{item.reason}</small>
                </div>
              ))}
            </div>
          )}
      </div>

      {(orchestration.blockers.length > 0 || orchestration.missing_information.length > 0) && (
        <div className="vn-grid vn-grid--two vn-section-gap">
          <div>
            <h4>O que bloqueou alternativas</h4>
            {orchestration.blockers.length > 0
              ? <ul>{orchestration.blockers.map((item) => <li key={`${item.code}-${item.fields.join('.')}`}>{item.message}</li>)}</ul>
              : <p>Nenhum bloqueio financeiro adicional.</p>}
          </div>
          <div>
            <h4>O que pode melhorar a decisão</h4>
            {orchestration.missing_information.length > 0
              ? <ul>{orchestration.missing_information.map((item) => <li key={`${item.code}-${item.fields.join('.')}`}>{item.message}</li>)}</ul>
              : <p>Nenhuma informação adicional necessária.</p>}
          </div>
        </div>
      )}

      {orchestration.warnings.length > 0 && (
        <div className="vn-section-gap">
          <h4>Pontos de atenção</h4>
          <ul>{orchestration.warnings.map((item) => <li key={`${item.code}-${item.fields.join('.')}`}>{item.message}</li>)}</ul>
        </div>
      )}

      {freezeErrorMessage && (
        <ErrorState
          title="Não foi possível salvar a estratégia"
          description={freezeErrorMessage}
          action={<Button variant="secondary" onClick={onFreeze}>Tentar novamente</Button>}
        />
      )}

      <div className="vn-section-gap">
        <h4>Estratégias salvas</h4>
        {historyErrorMessage
          ? (
            <ErrorState
              title="Não foi possível carregar o histórico"
              description={historyErrorMessage}
              action={<Button variant="secondary" onClick={onRetryHistory}>Tentar novamente</Button>}
            />
          )
          : isHistoryLoading
            ? <LoadingState label="Carregando estratégias salvas..." />
            : history && history.items.length > 0
              ? (
                <div className="vn-list" role="list" aria-label="Histórico de estratégias de investimento">
                  {history.items.slice(0, 5).map((item) => (
                    <div key={item.orchestration_id} role="listitem">
                      <strong>{statusLabels[item.status]}</strong>
                      <span>{new Date(item.generated_at).toLocaleString('pt-BR')} · sugerido: {money(item.suggested_capital)} · caixa: {money(item.remaining_investment_cash)}</span>
                    </div>
                  ))}
                </div>
              )
              : <p>Nenhuma estratégia foi congelada ainda.</p>}
      </div>
    </Card>
  );
}
