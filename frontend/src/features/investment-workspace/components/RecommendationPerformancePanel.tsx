import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Activity, BarChart3, ChevronDown, ChevronUp, Clock3, Gauge } from 'lucide-react';
import { Badge, Button, Card, EmptyState, ErrorState, LoadingState } from '../../../components';
import { getInvestmentPerformanceSummary } from '../services/investmentPerformance.service';
import type { PerformanceMetricGroup } from '../types/investmentWorkspace.types';

type Props = {
  userId?: number;
  refreshDecisionId?: string;
};

const horizonLabels: Record<string, string> = { '1d': '1 dia', '7d': '7 dias', '30d': '30 dias' };
const actionLabels: Record<string, string> = { BUY: 'Comprar', WAIT: 'Aguardar', AVOID: 'Evitar' };

function percentage(value: number | null | undefined, signed = false) {
  if (value === null || value === undefined || !Number.isFinite(value)) return '—';
  const prefix = signed && value > 0 ? '+' : '';
  return `${prefix}${value.toFixed(1).replace('.', ',')}%`;
}

function HorizonRow({ row }: { row: PerformanceMetricGroup }) {
  return (
    <li>
      <div><strong>{horizonLabels[row.key] ?? row.key}</strong><span>{row.evaluated} avaliadas · {row.pending} pendentes maduras</span></div>
      <dl>
        <div><dt>Retorno observado</dt><dd>{percentage(row.average_return_pct, true)}</dd></div>
        <div><dt>Consistência direcional</dt><dd>{percentage(row.directional_accuracy_pct)}</dd></div>
      </dl>
    </li>
  );
}

function ActionRow({ row }: { row: PerformanceMetricGroup }) {
  return (
    <article>
      <header><strong>{actionLabels[row.key] ?? row.key}</strong><Badge tone="neutral">{row.evaluated} avaliações</Badge></header>
      <span>Movimento posterior médio</span>
      <b>{percentage(row.average_return_pct, true)}</b>
      <small>Consistência direcional {percentage(row.directional_accuracy_pct)}</small>
    </article>
  );
}

export function RecommendationPerformancePanel({ userId, refreshDecisionId }: Props) {
  const [open, setOpen] = useState(false);
  const query = useQuery({
    queryKey: ['investment-performance', userId ?? 'anonymous', refreshDecisionId ?? 'none'],
    queryFn: ({ signal }) => getInvestmentPerformanceSummary(signal),
    enabled: open && Boolean(userId),
    retry: false,
    staleTime: 0,
  });

  return (
    <Card
      className="vn-performance-panel"
      title="Histórico de performance"
      description="Veja, quando os horizontes amadurecerem, o que aconteceu após as recomendações registradas."
      action={(
        <Button type="button" variant="secondary" aria-expanded={open} onClick={() => setOpen((value) => !value)}>
          <Activity size={17} aria-hidden="true" /> {open ? 'Ocultar performance' : 'Ver performance'} {open ? <ChevronUp size={15} /> : <ChevronDown size={15} />}
        </Button>
      )}
    >
      {open && (
        <div className="vn-performance-content" aria-live="polite">
          {query.isLoading && <LoadingState label="Conferindo horizontes e preços posteriores..." />}
          {query.error && <ErrorState title="Performance indisponível" description="As recomendações e seus snapshots continuam preservados. Tente consultar novamente." action={<Button type="button" variant="secondary" onClick={() => query.refetch()}>Tentar novamente</Button>} />}
          {query.data?.total_decisions === 0 && <EmptyState title="Ainda não há decisões históricas" description="Novas recomendações auditadas aparecerão aqui sem qualquer dado demonstrativo fictício." />}
          {query.data && query.data.total_decisions > 0 && (
            <>
              <div className="vn-performance-kpis">
                <article><Activity size={18} /><span>Avaliações concluídas</span><strong>{query.data.evaluated}</strong><small>observações por horizonte</small></article>
                <article><Clock3 size={18} /><span>Pendentes maduras</span><strong>{query.data.pending}</strong><small>aguardando preço compatível</small></article>
                <article><Gauge size={18} /><span>Consistência direcional</span><strong>{percentage(query.data.directional_accuracy_pct)}</strong><small>{query.data.directional_sample} resultados não neutros</small></article>
                <article><BarChart3 size={18} /><span>Retorno observado médio</span><strong>{percentage(query.data.average_return_pct, true)}</strong><small>movimento do ativo, não da carteira</small></article>
              </div>

              {query.data.evaluated === 0 ? (
                <EmptyState title="Horizontes ainda sem resultado" description={query.data.eligible_decisions === 0 ? 'As decisões registradas ainda não completaram 1, 7 ou 30 dias.' : 'Há horizontes maduros, mas ainda não existe um preço temporalmente compatível.'} />
              ) : (
                <div className="vn-performance-breakdown">
                  <section aria-labelledby="performance-horizons-title">
                    <h3 id="performance-horizons-title">Por horizonte</h3>
                    <ul className="vn-performance-horizons">{query.data.by_horizon.map((row) => <HorizonRow key={row.key} row={row} />)}</ul>
                  </section>
                  <section aria-labelledby="performance-actions-title">
                    <h3 id="performance-actions-title">Por decisão apresentada</h3>
                    <div className="vn-performance-actions">{query.data.by_action.map((row) => <ActionRow key={row.key} row={row} />)}</div>
                  </section>
                </div>
              )}

              {query.data.mixed_versions && <p className="vn-performance-version-note">A visão reúne versões diferentes. As métricas segmentadas por versão permanecem separadas no backend para evitar comparações silenciosas.</p>}
              <p className="vn-performance-disclaimer">Esta leitura observa o preço do ativo depois da recomendação. Não representa operação executada, rentabilidade de carteira, dividendos ou garantia de resultado.</p>
            </>
          )}
        </div>
      )}
    </Card>
  );
}
