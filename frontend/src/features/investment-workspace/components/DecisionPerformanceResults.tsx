import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Activity, Clock3 } from 'lucide-react';
import { Badge, Button, ErrorState, LoadingState } from '../../../components';
import { formatCurrency } from '../../../utils/formatters';
import { getInvestmentDecisionPerformance } from '../services/investmentPerformance.service';
import type { InvestmentPerformanceEvaluation, PerformanceClassification, PerformanceHorizon } from '../types/investmentWorkspace.types';

const horizonLabels: Record<PerformanceHorizon, string> = { '1d': '1 dia', '7d': '7 dias', '30d': '30 dias' };
const classificationLabels: Record<PerformanceClassification, string> = {
  STRONGLY_CORRECT: 'Muito coerente',
  CORRECT: 'Coerente',
  NEUTRAL: 'Neutro',
  INCORRECT: 'Incoerente',
  STRONGLY_INCORRECT: 'Muito incoerente',
};

function tone(classification: PerformanceClassification) {
  if (classification === 'STRONGLY_CORRECT' || classification === 'CORRECT') return 'success' as const;
  if (classification === 'NEUTRAL') return 'neutral' as const;
  return 'danger' as const;
}

function pct(value: number | string | null | undefined) {
  const converted = Number(value);
  if (value === null || value === undefined || !Number.isFinite(converted)) return '—';
  return `${converted > 0 ? '+' : ''}${converted.toFixed(2).replace('.', ',')}%`;
}

function shortDate(value: string) {
  return new Intl.DateTimeFormat('pt-BR', { dateStyle: 'short' }).format(new Date(value));
}

function EvaluationCard({ item }: { item: InvestmentPerformanceEvaluation }) {
  return (
    <article className="vn-performance-result-card">
      <header><strong>{horizonLabels[item.horizon]}</strong><Badge tone={tone(item.result_classification)}>{classificationLabels[item.result_classification]}</Badge></header>
      <div className="vn-performance-result-card__return"><span>Movimento observado</span><b>{pct(item.return_pct)}</b></div>
      <dl>
        <div><dt>Preço de referência</dt><dd>{formatCurrency(item.reference_price)}</dd></div>
        <div><dt>Preço no horizonte</dt><dd>{formatCurrency(item.evaluation_price)}</dd></div>
        <div><dt>Máx. favorável</dt><dd>{pct(item.max_favorable_excursion_pct)}</dd></div>
        <div><dt>Máx. adverso</dt><dd>{pct(item.max_adverse_excursion_pct)}</dd></div>
      </dl>
      <small>Avaliação em {shortDate(item.evaluation_timestamp)} · fonte {item.evaluation_price_source}</small>
    </article>
  );
}

export function DecisionPerformanceResults({ decisionId }: { decisionId: string }) {
  const [open, setOpen] = useState(false);
  const query = useQuery({
    queryKey: ['investment-performance', 'decision', decisionId],
    queryFn: ({ signal }) => getInvestmentDecisionPerformance(decisionId, signal),
    enabled: open,
    retry: false,
  });

  return (
    <section className="vn-decision-performance" aria-labelledby={`decision-performance-${decisionId}`}>
      <Button type="button" variant="secondary" aria-expanded={open} onClick={() => setOpen((value) => !value)}>
        <Activity size={16} /> {open ? 'Ocultar resultados posteriores' : 'Ver resultados posteriores'}
      </Button>
      {open && (
        <div className="vn-decision-performance__content">
          <h4 id={`decision-performance-${decisionId}`}>O que aconteceu depois</h4>
          {query.isLoading && <LoadingState label="Consultando preços posteriores sem recalcular a decisão..." />}
          {query.error && <ErrorState title="Resultado posterior indisponível" description="O snapshot original continua preservado e não foi alterado." />}
          {query.data && (
            <>
              {query.data.evaluations.length > 0 && <div className="vn-performance-results-grid">{query.data.evaluations.map((item) => <EvaluationCard key={item.horizon} item={item} />)}</div>}
              {query.data.evaluations.length === 0 && <p className="vn-performance-pending-copy"><Clock3 size={16} /> {query.data.eligible_pending_horizons.length > 0 ? 'Há horizonte maduro aguardando um preço temporalmente compatível.' : 'Os horizontes de 1, 7 e 30 dias ainda não amadureceram.'}</p>}
              {query.data.pending_horizons.length > 0 && <p className="vn-performance-pending-list">Pendentes: {query.data.pending_horizons.map((item) => horizonLabels[item]).join(', ')}.</p>}
              <p className="vn-performance-disclaimer">Classificação baseada no movimento posterior do ativo e na ação histórica {query.data.action}. Não é resultado de uma operação real.</p>
            </>
          )}
        </div>
      )}
    </section>
  );
}
