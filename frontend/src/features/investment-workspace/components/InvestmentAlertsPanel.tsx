import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Bell, CheckCheck, ChevronLeft, ChevronRight, Clock3, X } from 'lucide-react';
import { Badge, Button, Card, EmptyState, ErrorState, LoadingState } from '../../../components';
import type { ApiErrorShape } from '../../../services/api';
import {
  getInvestmentAlertDetail,
  getInvestmentAlerts,
  markInvestmentAlertRead,
} from '../services/investmentAlerts.service';
import type {
  DecisionAuditAction,
  InvestmentAlertDetail,
  InvestmentAlertSeverity,
  InvestmentAlertState,
  InvestmentAlertType,
} from '../types/investmentWorkspace.types';
import { riskLabel } from '../utils/investmentDecision';

type Props = { userId?: number };

const severityPresentation: Record<InvestmentAlertSeverity, { label: string; tone: 'neutral' | 'warning' | 'danger' }> = {
  INFO: { label: 'Informativo', tone: 'neutral' },
  MEDIUM: { label: 'Atenção', tone: 'warning' },
  HIGH: { label: 'Relevante', tone: 'danger' },
};

const typeLabels: Record<InvestmentAlertType, string> = {
  NEW_OPPORTUNITY: 'Nova oportunidade',
  ACTION_CHANGE: 'Mudança de recomendação',
  SCORE_CHANGE: 'Mudança de score',
  CONFIDENCE_CHANGE: 'Mudança de confiança',
  RISK_CHANGE: 'Mudança de risco',
};

const actionLabels: Record<DecisionAuditAction, string> = {
  BUY: 'Comprar',
  WAIT: 'Aguardar',
  AVOID: 'Evitar',
  NO_RECOMMENDATION: 'Sem recomendação',
};

function dateTime(value: string) {
  return new Intl.DateTimeFormat('pt-BR', { dateStyle: 'short', timeStyle: 'short' }).format(new Date(value));
}

function numeric(value: unknown) {
  if (value === null || value === undefined || value === '' || !Number.isFinite(Number(value))) return '—';
  return Number(value).toFixed(1).replace('.', ',');
}

function action(value: InvestmentAlertState['action']) {
  return value ? actionLabels[value] ?? value : '—';
}

function stateRisk(value: InvestmentAlertState['risk_level']) {
  return value ? riskLabel(value) : '—';
}

function alertError(error: unknown) {
  const apiError = error as ApiErrorShape | null;
  if (apiError?.status === 401 || apiError?.code === 'AUTH_EXPIRED') {
    return { title: 'Sessão encerrada', description: 'Entre novamente para consultar seus alertas.' };
  }
  return { title: 'Central de alertas indisponível', description: apiError?.message ?? 'Não foi possível consultar seus alertas agora.' };
}

function StateColumn({ title, state }: { title: string; state: InvestmentAlertState }) {
  return (
    <section className="vn-alert-state-column" aria-label={title}>
      <h4>{title}</h4>
      <dl>
        <div><dt>Recomendação</dt><dd>{action(state.action)}</dd></div>
        <div><dt>Score</dt><dd>{numeric(state.score ?? state.recommendation_score)}</dd></div>
        <div><dt>Confiança</dt><dd>{numeric(state.confidence)}</dd></div>
        <div><dt>Risco</dt><dd>{stateRisk(state.risk_level)}</dd></div>
      </dl>
    </section>
  );
}

function AlertDetail({ detail, pending, onClose, onMarkRead }: { detail: InvestmentAlertDetail; pending: boolean; onClose: () => void; onMarkRead: () => void }) {
  const severity = severityPresentation[detail.severity];
  return (
    <aside className="vn-alert-detail" aria-labelledby="alert-detail-title">
      <header>
        <div><span>{typeLabels[detail.alert_type]}</span><h3 id="alert-detail-title">{detail.asset}</h3><p>{dateTime(detail.created_at)}</p></div>
        <Button type="button" variant="ghost" aria-label="Fechar detalhe do alerta" onClick={onClose}><X size={17} /></Button>
      </header>
      <div className="vn-alert-detail__badges"><Badge tone={severity.tone}>{severity.label}</Badge><Badge tone={detail.read_at ? 'neutral' : 'warning'}>{detail.read_at ? 'Lido' : 'Não lido'}</Badge></div>
      <p className="vn-alert-detail__message">{detail.message}</p>
      <div className="vn-alert-state-comparison">
        <StateColumn title="Antes" state={detail.previous_state} />
        <StateColumn title="Agora" state={detail.current_state} />
      </div>
      <div className="vn-alert-detail__trace"><span>Decisão relacionada</span><code>{detail.decision_id}</code></div>
      {!detail.read_at && <Button type="button" disabled={pending} onClick={onMarkRead}><CheckCheck size={17} /> {pending ? 'Marcando...' : 'Marcar como lido'}</Button>}
    </aside>
  );
}

export function InvestmentAlertsPanel({ userId }: Props) {
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const [page, setPage] = useState(1);
  const [unreadOnly, setUnreadOnly] = useState(false);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const identity = userId ?? 'anonymous';
  const summaryQuery = useQuery({
    queryKey: ['investment-alerts', identity, 'summary'],
    queryFn: ({ signal }) => getInvestmentAlerts({ page: 1, pageSize: 1 }, signal),
    enabled: Boolean(userId),
    retry: false,
    staleTime: 30_000,
  });
  const alertsQuery = useQuery({
    queryKey: ['investment-alerts', identity, 'inbox', page, unreadOnly],
    queryFn: ({ signal }) => getInvestmentAlerts({ page, pageSize: 8, unreadOnly }, signal),
    enabled: open && Boolean(userId),
    retry: false,
    staleTime: 0,
  });
  const detailQuery = useQuery({
    queryKey: ['investment-alerts', identity, 'detail', selectedId],
    queryFn: ({ signal }) => getInvestmentAlertDetail(selectedId!, signal),
    enabled: open && Boolean(userId && selectedId),
    retry: false,
  });
  const markRead = useMutation({
    mutationFn: () => markInvestmentAlertRead(selectedId!),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['investment-alerts', identity] });
    },
  });
  const unreadCount = alertsQuery.data?.unread_count ?? summaryQuery.data?.unread_count ?? 0;
  const error = alertError(alertsQuery.error);

  return (
    <Card
      className="vn-alerts-panel"
      title="Central de alertas"
      description="Mudanças relevantes das oportunidades que você decidiu acompanhar."
      action={(
        <Button type="button" variant="secondary" aria-expanded={open} onClick={() => setOpen((value) => !value)}>
          <Bell size={17} aria-hidden="true" /> {open ? 'Ocultar alertas' : 'Abrir alertas'}
          {unreadCount > 0 && <span className="vn-alert-count" aria-label={`${unreadCount} alertas não lidos`}>{unreadCount > 99 ? '99+' : unreadCount}</span>}
        </Button>
      )}
    >
      {open && (
        <div className="vn-alerts-content">
          <div className="vn-alerts-toolbar">
            <label className="vn-check"><input type="checkbox" checked={unreadOnly} onChange={(event) => { setUnreadOnly(event.target.checked); setPage(1); setSelectedId(null); }} /><span>Mostrar somente não lidos</span></label>
            <span>{unreadCount === 0 ? 'Tudo em dia' : `${unreadCount} não ${unreadCount === 1 ? 'lido' : 'lidos'}`}</span>
          </div>
          <div className="vn-alerts-layout">
            <div className="vn-alerts-list" aria-live="polite">
              {alertsQuery.isLoading && <LoadingState label="Carregando seus alertas..." />}
              {alertsQuery.error && <ErrorState title={error.title} description={error.description} action={<Button type="button" variant="secondary" onClick={() => alertsQuery.refetch()}>Tentar novamente</Button>} />}
              {alertsQuery.data?.items.length === 0 && (
                <EmptyState
                  title={unreadOnly ? 'Todos os alertas foram lidos' : 'Nenhum alerta por enquanto'}
                  description={unreadOnly ? 'Desative o filtro para consultar o histórico completo.' : 'Quando uma mudança relevante superar seus critérios, ela aparecerá aqui.'}
                />
              )}
              {alertsQuery.data && alertsQuery.data.items.length > 0 && (
                <>
                  <ol>
                    {alertsQuery.data.items.map((item) => {
                      const severity = severityPresentation[item.severity];
                      return (
                        <li key={item.alert_id}>
                          <button type="button" aria-current={selectedId === item.alert_id ? 'true' : undefined} onClick={() => setSelectedId(item.alert_id)}>
                            <span className="vn-alert-item__top"><strong>{item.asset}</strong><Badge tone={severity.tone}>{severity.label}</Badge></span>
                            <span className="vn-alert-item__type">{typeLabels[item.alert_type]}{!item.read_at && <i aria-label="Não lido" />}</span>
                            <span className="vn-alert-item__message">{item.message}</span>
                            <span className="vn-alert-item__time"><Clock3 size={14} aria-hidden="true" /> {dateTime(item.created_at)}</span>
                          </button>
                        </li>
                      );
                    })}
                  </ol>
                  {alertsQuery.data.total_pages > 1 && (
                    <nav className="vn-history-pagination" aria-label="Paginação dos alertas">
                      <Button type="button" variant="ghost" disabled={page <= 1} onClick={() => { setSelectedId(null); setPage((value) => Math.max(1, value - 1)); }}><ChevronLeft size={16} /> Anterior</Button>
                      <span>Página {page} de {alertsQuery.data.total_pages}</span>
                      <Button type="button" variant="ghost" disabled={page >= alertsQuery.data.total_pages} onClick={() => { setSelectedId(null); setPage((value) => value + 1); }}>Próxima <ChevronRight size={16} /></Button>
                    </nav>
                  )}
                </>
              )}
            </div>
            {selectedId && (
              <div className="vn-alert-detail-region">
                {detailQuery.isLoading && <LoadingState label="Abrindo contexto do alerta..." />}
                {detailQuery.error && <ErrorState title="Detalhe indisponível" description="O alerta não foi encontrado ou não pertence a esta conta." action={<Button type="button" variant="secondary" onClick={() => setSelectedId(null)}>Voltar aos alertas</Button>} />}
                {detailQuery.data && <AlertDetail detail={detailQuery.data} pending={markRead.isPending} onClose={() => setSelectedId(null)} onMarkRead={() => markRead.mutate()} />}
                {markRead.error && <p className="vn-monitoring-error" role="alert">{alertError(markRead.error).description}</p>}
              </div>
            )}
          </div>
        </div>
      )}
    </Card>
  );
}
