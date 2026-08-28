import { AllocationCard, Badge, Button, Card, EmptyPortfolioState, EmptyState, ErrorState, LoadingState, MetricCard, RecommendationCard, SectionHeader, WarningCard } from '../components';
import { useRecommendations } from '../features/intelligence/hooks/useIntelligence';
import type { ApiErrorShape } from '../services/api';
import { formatCurrency } from '../utils/formatters';

const labels: Record<string, string> = { renda_fixa: 'Renda fixa', fii: 'FIIs', acoes: 'Ações', etf: 'ETFs', bdr: 'BDRs', cripto: 'Cripto' };

function isMissingContext(error: unknown) {
  const apiError = error as ApiErrorShape | null;
  return Boolean(apiError && [400, 404, 422].includes(apiError.status));
}

function riskExplanation(warnings: string[]) {
  if (warnings.some((warning) => warning.toLowerCase().includes('cripto'))) return 'A exposição a cripto pode ser zerada por score, perfil ou restrição de risco.';
  if (warnings.length > 0) return 'O backend ajustou a leitura de risco usando restrições financeiras reais.';
  return 'A alocação segue o perfil e o diagnóstico atual sem alerta crítico retornado.';
}

export function IntelligencePage() {
  const recommendations = useRecommendations();
  const error = recommendations.error as ApiErrorShape | null;
  const missingContext = isMissingContext(error);

  return <section className="vn-page">
    <SectionHeader eyebrow="Inteligência" title="Allocation e ranking educacional." description="Leitura real da camada heurística aprovada na Fase 6, sem promessa financeira e sem recomendação definitiva." />
    {recommendations.isLoading && <Card><LoadingState label="Carregando recomendações heurísticas..." /></Card>}
    {missingContext && <Card><EmptyPortfolioState /></Card>}
    {error && !missingContext && <Card><ErrorState title="Inteligência ainda indisponível" description={error.message} action={<Button variant="secondary" onClick={() => recommendations.refetch()}>Tentar novamente</Button>} /></Card>}
    {recommendations.data && <>
      <div className="vn-metrics vn-metrics--refined">
        <MetricCard label="Score financeiro" value={recommendations.data.financial_score} helper="Base de restrição usada pela inteligência." badge="backend" />
        <MetricCard label="Capacidade" value={formatCurrency(recommendations.data.investment_capacity)} helper="Valor de aporte mensal considerado." badge="mensal" />
        <MetricCard label="Perfil ajustado" value={recommendations.data.adjusted_risk_profile} helper="Perfil após score, reserva e regras de risco." badge="restrições" tone="warning" />
      </div>
      <div className="vn-grid vn-grid--two">
        <AllocationCard labels={labels} items={recommendations.data.allocation} />
        <Card title="Por que a alocação pode mudar?" description="Explicação curta, educacional e sem promessa de retorno.">
          <div className="vn-insight-list">
            <WarningCard title="Score financeiro" description="Score baixo tende a priorizar estabilidade, reserva e renda fixa antes de risco." />
            <WarningCard title="Cripto e risco alto" description={riskExplanation(recommendations.data.warnings)} />
            <WarningCard title="Metodologia" description={recommendations.data.methodology[0] || 'Scoring heurístico com dados disponíveis e tratamento neutro para campos ausentes.'} tone="success" />
          </div>
        </Card>
      </div>
      {recommendations.data.warnings.length > 0 && <Card title="Warnings de risco" description="Sinais enviados pelo backend para limitar interpretação agressiva."><div className="vn-warning-grid">{recommendations.data.warnings.map((warning) => <WarningCard key={warning} description={warning} />)}</div></Card>}
      <div className="vn-grid vn-grid--three vn-section-gap">
        {recommendations.data.recommendations_by_class.map((group) => <RecommendationCard key={group.asset_class} assetClass={group.asset_class} label={labels[group.asset_class] ?? group.asset_class} allocationPercentage={group.allocation_percentage} allocationAmount={group.allocation_amount} assets={group.assets} message={group.message} />)}
        {recommendations.data.recommendations_by_class.length === 0 && <Card><EmptyState title="Sem classes recomendadas" description="O backend não retornou classes para o contexto atual." /></Card>}
      </div>
      <Card title="Metodologia retornada" description="Registro textual para transparência do cálculo.">
        <div className="vn-list">{recommendations.data.methodology.map((item) => <div key={item}><strong>{item}</strong><span>Regra educacional aplicada pelo backend.</span></div>)}{recommendations.data.methodology.length === 0 && <EmptyState title="Sem metodologia retornada" description="O backend não retornou detalhes metodológicos." />}</div>
      </Card>
    </>}
  </section>;
}
