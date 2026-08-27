import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { BarChart3, GitCompareArrows, Lightbulb, Sparkles } from 'lucide-react';
import { Badge, Button, Card, EmptyState, ErrorState, LoadingState, SectionHeader } from '../components';
import {
  AlternativesComparison,
  AttentionPointsCard,
  BudgetUsageCard,
  DecisionHistoryPanel,
  DecisionHeroCard,
  DecisionTraceMeta,
  ExecutiveSummaryCard,
  InvestmentAlertsPanel,
  InvestmentMonitoringControl,
  QuantChanceCard,
  RecommendationPerformancePanel,
  ScoreBreakdownBars,
  StrengthChecklist,
  TrendInterpreterCard,
} from '../features/investment-workspace/components';
import { useCurrentUser } from '../features/auth/hooks/useAuth';
import { getInvestmentWorkspaceRecommendation } from '../features/investment-workspace/services/investmentWorkspace.service';
import type { ExplainedBudgetAdvisorResponse, InvestmentWorkspaceFilters, InvestorProfile } from '../features/investment-workspace/types/investmentWorkspace.types';
import { decisionPresentation } from '../features/investment-workspace/utils/investmentDecision';
import type { ApiErrorShape } from '../services/api';

const marketOptions = [
  { value: 'FII', label: 'FIIs' },
  { value: 'ACOES', label: 'Ações' },
  { value: 'ETF', label: 'ETFs' },
  { value: 'BDR', label: 'BDRs' },
];

const profileOptions: Array<{ value: InvestorProfile; label: string }> = [
  { value: 'CONSERVATIVE', label: 'Conservador' },
  { value: 'MODERATE', label: 'Moderado' },
  { value: 'AGGRESSIVE', label: 'Agressivo' },
];

function DecisionSectionTitle({ icon: Icon, eyebrow, title, description, id }: { icon: typeof BarChart3; eyebrow: string; title: string; description: string; id: string }) {
  return (
    <header className="vn-decision-section-title">
      <span><Icon size={17} aria-hidden="true" /> {eyebrow}</span>
      <h2 id={id}>{title}</h2>
      <p>{description}</p>
    </header>
  );
}

function WorkspaceResult({ data, userId }: { data: ExplainedBudgetAdvisorResponse; userId?: number }) {
  const best = data.best_recommendation;
  if (!best) {
    return (
      <Card>
        <EmptyState title="Nenhuma recomendação disponível" description="Não encontramos ativos compatíveis com o orçamento, mercado e perfil informados." />
        <DecisionTraceMeta decisionId={data.decision_id} correlationId={data.correlation_id} generatedAt={data.generated_at} auditStatus={data.audit_status} />
      </Card>
    );
  }
  const presentation = decisionPresentation(best);
  const isBuy = presentation.action.label === 'Comprar';
  const overviewTitle = isBuy
    ? 'Entenda a oportunidade em poucos segundos'
    : presentation.action.label === 'Evitar'
      ? 'Entenda por que a compra não é indicada'
      : 'Entenda por que é melhor aguardar';
  const explanationTitle = isBuy ? 'Por que este ativo foi escolhido' : 'Quais sinais sustentam esta decisão';

  return (
    <div className="vn-investment-result" role="region" aria-label={`Decisão de investimento para ${best.ticker}`}>
      {data.integration_warnings && data.integration_warnings.length > 0 && (
        <Card className="vn-partial-response-card">
          <div role="status"><strong>Dados parciais recebidos</strong><ul>{data.integration_warnings.map((warning) => <li key={warning}>{warning}</li>)}</ul></div>
        </Card>
      )}
      <DecisionHeroCard item={best} presentation={presentation} />
      <DecisionTraceMeta decisionId={data.decision_id} correlationId={data.correlation_id} generatedAt={data.generated_at} auditStatus={data.audit_status} />
      <InvestmentMonitoringControl userId={userId} asset={best.ticker} decisionId={data.decision_id} />

      <section className="vn-decision-section" aria-labelledby="decision-overview-title">
        <DecisionSectionTitle
          icon={BarChart3}
          eyebrow="Decisão"
          id="decision-overview-title"
          title={overviewTitle}
          description="Chance, orçamento, risco, tendência e potencial reunidos em uma leitura objetiva."
        />
        <div className="vn-decision-overview-grid">
          <QuantChanceCard item={best} presentation={presentation} />
          <BudgetUsageCard item={best} budget={data.budget} presentation={presentation} />
          <TrendInterpreterCard item={best} presentation={presentation} />
        </div>
        <ExecutiveSummaryCard item={best} presentation={presentation} />
      </section>

      <section className="vn-decision-section" aria-labelledby="decision-explanation-title">
        <DecisionSectionTitle
          icon={Lightbulb}
          eyebrow="Explicação"
          id="decision-explanation-title"
          title={explanationTitle}
          description="Veja os critérios, os pontos fortes e as ressalvas que sustentam a leitura."
        />
        <div className="vn-explanation-grid">
          <ScoreBreakdownBars breakdown={best.score_breakdown} item={best} />
          <StrengthChecklist title="Motivos da recomendação" items={best.why_recommended} variant="reasons" />
        </div>
        <div className="vn-explanation-grid vn-explanation-grid--balanced">
          <StrengthChecklist title="Pontos fortes" items={best.strengths} />
          <AttentionPointsCard items={best.attention_points} />
        </div>
      </section>

      <section className="vn-decision-section" aria-labelledby="decision-alternatives-title">
        <DecisionSectionTitle
          icon={GitCompareArrows}
          eyebrow="Alternativas"
          id="decision-alternatives-title"
          title="Compare antes de decidir"
          description="Entenda a posição da primeira opção e conheça os demais ativos avaliados no ranking."
        />
        <AlternativesComparison comparison={best.comparison_with_alternatives} alternatives={data.alternatives} />
      </section>

      {(data.disclaimer ?? best.disclaimer) && (
        <Card className="vn-disclaimer-card"><p>{data.disclaimer ?? best.disclaimer}</p></Card>
      )}
    </div>
  );
}

function useInvestmentWorkspace(filters: InvestmentWorkspaceFilters, enabled: boolean, userId: number | undefined, requestSequence: number) {
  return useQuery({
    queryKey: ['investment-workspace', userId ?? 'anonymous', filters, requestSequence],
    queryFn: ({ signal }) => getInvestmentWorkspaceRecommendation(filters, signal),
    enabled,
    staleTime: 0,
    retry: false,
    placeholderData: (previousData) => previousData,
  });
}

export function investmentErrorPresentation(error: ApiErrorShape | null) {
  if (error?.code === 'TIMEOUT') return { title: 'A análise demorou mais que o esperado', description: error.message };
  if (error?.code === 'INVALID_RESPONSE') return { title: 'Resposta inesperada da API', description: 'Os dados recebidos não puderam ser validados com segurança. Tente novamente.' };
  if (error?.code === 'NETWORK_ERROR' || error?.status === 0) return { title: 'Serviço temporariamente indisponível', description: error?.message ?? 'Não foi possível alcançar a API.' };
  return { title: 'Não foi possível gerar a recomendação', description: error?.message ?? 'Falha inesperada ao consultar a recomendação.' };
}

function InvestmentWorkspaceContent({ userId }: { userId?: number }) {
  const [filters, setFilters] = useState<InvestmentWorkspaceFilters>({ budget: 300, market: 'FII', profile: 'CONSERVATIVE', includeWarnings: false });
  const [submittedFilters, setSubmittedFilters] = useState<InvestmentWorkspaceFilters>(filters);
  const [hasSubmitted, setHasSubmitted] = useState(false);
  const [requestSequence, setRequestSequence] = useState(0);
  const query = useInvestmentWorkspace(submittedFilters, hasSubmitted, userId, requestSequence);
  const error = query.error as ApiErrorShape | null;
  const errorContent = investmentErrorPresentation(error);

  function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmittedFilters({ ...filters });
    setHasSubmitted(true);
    setRequestSequence((value) => value + 1);
  }

  return (
    <section className="vn-page vn-investment-workspace">
      <SectionHeader
        eyebrow="Investir"
        headingLevel={1}
        title="Central de decisão de investimentos"
        description="Informe quanto pretende investir e receba uma leitura direta da melhor oportunidade para seu perfil."
        action={<Badge tone="success">Análise quantitativa</Badge>}
      />

      <Card className="vn-investment-filters" title="Encontre a melhor oportunidade" description="Defina o orçamento, mercado e perfil para consultar o Budget Advisor.">
        <form className="vn-investment-filter-grid" onSubmit={submit}>
          <label className="vn-field">
            Orçamento
            <input
              className="vn-input"
              type="number"
              inputMode="decimal"
              min="1"
              step="0.01"
              required
              value={filters.budget}
              onChange={(event) => setFilters((current) => ({ ...current, budget: Number(event.target.value) }))}
            />
          </label>
          <label className="vn-field">
            Mercado
            <select className="vn-input" value={filters.market} onChange={(event) => setFilters((current) => ({ ...current, market: event.target.value }))}>
              {marketOptions.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
            </select>
          </label>
          <label className="vn-field">
            Perfil
            <select className="vn-input" value={filters.profile} onChange={(event) => setFilters((current) => ({ ...current, profile: event.target.value as InvestorProfile }))}>
              {profileOptions.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
            </select>
          </label>
          <label className="vn-check vn-investment-warning-toggle">
            <input type="checkbox" checked={filters.includeWarnings} onChange={(event) => setFilters((current) => ({ ...current, includeWarnings: event.target.checked }))} />
            <span>Incluir ativos com alerta</span>
          </label>
          <Button type="submit" disabled={query.isFetching}><Sparkles size={17} aria-hidden="true" /> {query.isFetching ? 'Analisando...' : 'Analisar orçamento'}</Button>
        </form>
      </Card>

      <InvestmentAlertsPanel userId={userId} />
      <DecisionHistoryPanel userId={userId} refreshDecisionId={query.data?.decision_id} />
      <RecommendationPerformancePanel userId={userId} refreshDecisionId={query.data?.decision_id} />

      {!hasSubmitted && <Card><EmptyState title="Pronto para analisar" description="Informe seu orçamento e clique em Analisar orçamento para descobrir a melhor oportunidade disponível." /></Card>}
      <div className={query.isFetching && query.data ? 'vn-query-region vn-query-region--refreshing' : 'vn-query-region'} aria-busy={query.isFetching}>
        {query.isFetching && query.data && <div className="vn-refresh-notice" role="status">Atualizando análise — o resultado abaixo ainda é o anterior.</div>}
        {query.isLoading && <Card><LoadingState label="Comparando oportunidades para seu perfil..." /></Card>}
        {error && <Card><ErrorState title={errorContent.title} description={`${errorContent.description}${error.correlationId ? ` Código de suporte: ${error.correlationId}.` : ''}`} action={<Button variant="secondary" onClick={() => setRequestSequence((value) => value + 1)}>Tentar novamente</Button>} /></Card>}
        {hasSubmitted && query.data && !query.isLoading && !error && <WorkspaceResult data={query.data} userId={userId} />}
      </div>
    </section>
  );
}

export function InvestmentWorkspacePage() {
  const currentUser = useCurrentUser();
  const userId = currentUser.data?.id;
  return <InvestmentWorkspaceContent key={userId ?? 'authenticated-session'} userId={userId} />;
}
