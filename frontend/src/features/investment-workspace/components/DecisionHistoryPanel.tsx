import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { ChevronLeft, ChevronRight, Clock3, History, ShieldCheck, X } from 'lucide-react';
import { Badge, Button, Card, EmptyState, ErrorState, LoadingState } from '../../../components';
import { formatCurrency } from '../../../utils/formatters';
import { getInvestmentDecisionDetail, getInvestmentDecisionHistory } from '../services/investmentDecisionHistory.service';
import type { DecisionAuditAction, InvestmentDecisionDetail } from '../types/investmentWorkspace.types';
import { riskLabel, riskTone } from '../utils/investmentDecision';
import { DecisionPerformanceResults } from './DecisionPerformanceResults';

type Props = {
  userId?: number;
  refreshDecisionId?: string;
};

const actionPresentation: Record<string, { label: string; tone: 'success' | 'warning' | 'danger' | 'neutral' }> = {
  BUY: { label: 'Comprar', tone: 'success' },
  WAIT: { label: 'Aguardar', tone: 'warning' },
  AVOID: { label: 'Evitar', tone: 'danger' },
  NO_RECOMMENDATION: { label: 'Sem recomendação', tone: 'neutral' },
};

function actionLabel(action: DecisionAuditAction) {
  return actionPresentation[action] ?? { label: action || 'Indefinida', tone: 'neutral' as const };
}

function dateTime(value: string) {
  return new Intl.DateTimeFormat('pt-BR', { dateStyle: 'short', timeStyle: 'short' }).format(new Date(value));
}

function metric(value: number | string | null | undefined, suffix = '') {
  if (value === null || value === undefined || !Number.isFinite(Number(value))) return '—';
  return `${Number(value).toFixed(1).replace('.', ',')}${suffix}`;
}

function explanationSummary(detail: InvestmentDecisionDetail) {
  const summary = detail.explanation.executive_summary ?? detail.explanation.decision_summary;
  return typeof summary === 'string' && summary.trim() ? summary : 'O snapshot não contém um resumo textual.';
}

function DecisionDetail({ detail, onClose }: { detail: InvestmentDecisionDetail; onClose: () => void }) {
  const action = actionLabel(detail.recommendation);
  return (
    <aside className="vn-history-detail" aria-labelledby="history-detail-title">
      <header>
        <div>
          <span>Snapshot imutável</span>
          <h3 id="history-detail-title">{detail.asset ?? 'Decisão sem ativo'}</h3>
          <p>{dateTime(detail.created_at)}</p>
        </div>
        <Button type="button" variant="ghost" onClick={onClose} aria-label="Fechar detalhe da decisão"><X size={17} /></Button>
      </header>
      <div className="vn-history-detail__badges">
        <Badge tone={action.tone}>{action.label}</Badge>
        <Badge tone={riskTone(detail.risk_level)}>{riskLabel(detail.risk_level)}</Badge>
        {detail.fallback_used && <Badge tone="warning">Fallback</Badge>}
      </div>
      <dl className="vn-history-detail__metrics">
        <div><dt>Valor</dt><dd>{detail.invested_amount == null ? '—' : formatCurrency(detail.invested_amount)}</dd></div>
        <div><dt>Score</dt><dd>{metric(detail.recommendation_score)}</dd></div>
        <div><dt>Confiança</dt><dd>{metric(detail.confidence)}</dd></div>
        <div><dt>Latência</dt><dd>{detail.latency_ms} ms</dd></div>
      </dl>
      <p className="vn-history-detail__summary">{explanationSummary(detail)}</p>
      <div className="vn-history-detail__versions">
        <ShieldCheck size={16} aria-hidden="true" />
        <span>Engine {detail.recommendation_engine_version} · Regras {detail.rule_version}</span>
      </div>
      <DecisionPerformanceResults decisionId={detail.decision_id} />
      <details className="vn-decision-trace">
        <summary>Rastreabilidade completa</summary>
        <dl>
          <div><dt>Decision ID</dt><dd><code>{detail.decision_id}</code></dd></div>
          <div><dt>Correlation ID</dt><dd><code>{detail.correlation_id}</code></dd></div>
          <div><dt>Schema</dt><dd><code>{detail.snapshot_schema_version}</code></dd></div>
          <div><dt>Score</dt><dd><code>{detail.score_version ?? '—'}</code></dd></div>
          <div><dt>Guardrail</dt><dd><code>{detail.guardrail_version ?? '—'}</code></dd></div>
          <div><dt>Tendência</dt><dd><code>{detail.trend_version ?? '—'}</code></dd></div>
        </dl>
      </details>
    </aside>
  );
}

export function DecisionHistoryPanel({ userId, refreshDecisionId }: Props) {
  const [open, setOpen] = useState(false);
  const [page, setPage] = useState(1);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const historyQuery = useQuery({
    queryKey: ['investment-decisions', userId ?? 'anonymous', 'history', page, refreshDecisionId ?? 'none'],
    queryFn: ({ signal }) => getInvestmentDecisionHistory(page, 5, signal),
    enabled: open && Boolean(userId),
    retry: false,
    staleTime: 0,
  });
  const detailQuery = useQuery({
    queryKey: ['investment-decisions', userId ?? 'anonymous', 'detail', selectedId],
    queryFn: ({ signal }) => getInvestmentDecisionDetail(selectedId!, signal),
    enabled: open && Boolean(userId && selectedId),
    retry: false,
  });

  return (
    <Card
      className="vn-decision-history"
      title="Histórico de decisões"
      description="Consulte as análises registradas para esta conta."
      action={<Button type="button" variant="secondary" aria-expanded={open} onClick={() => setOpen((value) => !value)}><History size={17} /> {open ? 'Ocultar histórico' : 'Ver histórico'}</Button>}
    >
      {open && (
        <div className="vn-history-layout">
          <div className="vn-history-list" aria-live="polite">
            {historyQuery.isLoading && <LoadingState label="Carregando decisões recentes..." />}
            {historyQuery.error && <ErrorState title="Não foi possível carregar o histórico" description="A decisão atual continua disponível. Tente carregar o histórico novamente." action={<Button type="button" variant="secondary" onClick={() => historyQuery.refetch()}>Tentar novamente</Button>} />}
            {historyQuery.data?.items.length === 0 && <EmptyState title="Histórico vazio" description="Sua próxima análise registrada aparecerá aqui." />}
            {historyQuery.data && historyQuery.data.items.length > 0 && (
              <>
                <ol>
                  {historyQuery.data.items.map((item) => {
                    const action = actionLabel(item.recommendation);
                    return (
                      <li key={item.decision_id}>
                        <button type="button" aria-current={selectedId === item.decision_id ? 'true' : undefined} onClick={() => setSelectedId(item.decision_id)}>
                          <span className="vn-history-item__top"><strong>{item.asset ?? 'Sem ativo'}</strong><Badge tone={action.tone}>{action.label}</Badge></span>
                          <span className="vn-history-item__time"><Clock3 size={14} /> {dateTime(item.created_at)}</span>
                          <span className="vn-history-item__metrics">
                            <span>{item.invested_amount == null ? '—' : formatCurrency(item.invested_amount)}</span>
                            <span>Score {metric(item.recommendation_score)}</span>
                            <span>{riskLabel(item.risk_level)}</span>
                            <span>Conf. {metric(item.confidence)}</span>
                          </span>
                        </button>
                      </li>
                    );
                  })}
                </ol>
                {historyQuery.data.total_pages > 1 && (
                  <nav className="vn-history-pagination" aria-label="Paginação do histórico">
                    <Button type="button" variant="ghost" disabled={page <= 1} onClick={() => { setSelectedId(null); setPage((value) => Math.max(1, value - 1)); }}><ChevronLeft size={16} /> Anterior</Button>
                    <span>Página {page} de {historyQuery.data.total_pages}</span>
                    <Button type="button" variant="ghost" disabled={page >= historyQuery.data.total_pages} onClick={() => { setSelectedId(null); setPage((value) => value + 1); }}>Próxima <ChevronRight size={16} /></Button>
                  </nav>
                )}
              </>
            )}
          </div>
          {selectedId && (
            <div className="vn-history-detail-region">
              {detailQuery.isLoading && <LoadingState label="Abrindo snapshot da decisão..." />}
              {detailQuery.error && <ErrorState title="Detalhe indisponível" description="A decisão não foi encontrada ou não pertence a esta conta." action={<Button type="button" variant="secondary" onClick={() => setSelectedId(null)}>Voltar ao histórico</Button>} />}
              {detailQuery.data && <DecisionDetail detail={detailQuery.data} onClose={() => setSelectedId(null)} />}
            </div>
          )}
        </div>
      )}
    </Card>
  );
}
