import { AllocationCard, Badge, Button, Card, EmptyPortfolioState, EmptyState, ErrorState, LoadingState, MetricCard, RecommendationCard, SectionHeader, WarningCard } from '../components';
import { useRecommendations } from '../features/intelligence/hooks/useIntelligence';
import { presentIntelligenceWarning, riskProfileLabel } from '../features/intelligence/utils/presentation';
import type { ApiErrorShape } from '../services/api';
import { formatCurrency } from '../utils/formatters';

const labels: Record<string, string> = { renda_fixa: 'Renda fixa', fii: 'FIIs', acoes: 'Ações', etf: 'ETFs', bdr: 'BDRs', cripto: 'Cripto' };

function isMissingContext(error: unknown) {
  const apiError = error as ApiErrorShape | null;
  return Boolean(apiError && [400, 404, 422].includes(apiError.status));
}

function riskExplanation(warnings: string[]) {
  if (warnings.some((warning) => warning.toLowerCase().includes('cripto'))) return 'A exposição a cripto pode ser zerada pela pontuação financeira, pelo perfil ou por restrições de risco.';
  if (warnings.length > 0) return 'A leitura de risco foi limitada pelas restrições financeiras identificadas.';
  return 'A alocação segue o perfil e o diagnóstico atual sem alerta crítico retornado.';
}

export function IntelligencePage() {
  const recommendations = useRecommendations();
  const error = recommendations.error as ApiErrorShape | null;
  const missingContext = isMissingContext(error);

  return <section className="vn-page">
    <SectionHeader eyebrow="Análises" title="Como seus dados orientam a alocação" description="Uma leitura explicável da capacidade de aporte, do perfil e das restrições atuais. Não é promessa de retorno nem ordem de compra." />
    {recommendations.isLoading && <Card><LoadingState label="Analisando os dados disponíveis..." /></Card>}
    {missingContext && <Card><EmptyPortfolioState /></Card>}
    {error && !missingContext && <Card><ErrorState title="Inteligência ainda indisponível" description={error.message} action={<Button variant="secondary" onClick={() => recommendations.refetch()}>Tentar novamente</Button>} /></Card>}
    {recommendations.data && <>
      <div className="vn-metrics vn-metrics--refined">
        <MetricCard label="Pontuação financeira" value={recommendations.data.financial_score} helper="Indicador usado para dimensionar segurança e capacidade." badge="dados atuais" />
        <MetricCard label="Capacidade" value={formatCurrency(recommendations.data.investment_capacity)} helper="Valor de aporte mensal considerado." badge="mensal" />
        <MetricCard label="Perfil ajustado" value={riskProfileLabel(recommendations.data.adjusted_risk_profile)} helper="Perfil após considerar pontuação, reserva e regras de risco." badge="restrições" tone="warning" />
      </div>
      <div className="vn-grid vn-grid--two">
        <AllocationCard labels={labels} items={recommendations.data.allocation} />
        <Card title="Por que a alocação pode mudar?" description="Explicação curta, educacional e sem promessa de retorno.">
          <div className="vn-insight-list">
            <WarningCard title="Pontuação financeira" description="Uma pontuação baixa tende a priorizar estabilidade, reserva e renda fixa antes de mais risco." />
            <WarningCard title="Cripto e risco alto" description={riskExplanation(recommendations.data.warnings)} />
            <WarningCard title="Metodologia" description={recommendations.data.methodology[0] || 'Scoring heurístico com dados disponíveis e tratamento neutro para campos ausentes.'} tone="success" />
          </div>
        </Card>
      </div>
      {recommendations.data.warnings.length > 0 && <Card title="O que limita esta análise" description="Dados ausentes e restrições que impedem uma decisão mais completa."><div className="vn-warning-grid">{recommendations.data.warnings.map((warning) => <WarningCard key={warning} description={presentIntelligenceWarning(warning)} />)}</div></Card>}
      <div className="vn-grid vn-grid--three vn-section-gap">
        {recommendations.data.recommendations_by_class.map((group) => <RecommendationCard key={group.asset_class} assetClass={group.asset_class} label={labels[group.asset_class] ?? group.asset_class} allocationPercentage={group.allocation_percentage} allocationAmount={group.allocation_amount} assets={group.assets} message={group.message} />)}
        {recommendations.data.recommendations_by_class.length === 0 && <Card><EmptyState title="Sem classes compatíveis agora" description="Os dados e limites atuais não sustentam uma sugestão de classe de investimento." /></Card>}
      </div>
      <Card title="Como chegamos a esta leitura" description="Regras consideradas para tornar a análise verificável.">
        <div className="vn-list">{recommendations.data.methodology.map((item) => <div key={item}><strong>{presentIntelligenceWarning(item)}</strong><span>Critério educacional aplicado aos dados disponíveis.</span></div>)}{recommendations.data.methodology.length === 0 && <EmptyState title="Critérios não detalhados" description="A análise não retornou detalhes adicionais de metodologia." />}</div>
      </Card>
    </>}
  </section>;
}
