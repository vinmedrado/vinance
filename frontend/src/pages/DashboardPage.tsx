import { ArrowUpRight, PiggyBank, ShieldCheck, WalletCards } from 'lucide-react';
import { AllocationCard, Button, Card, EmptyState, ErrorState, LoadingState, MetricCard, OnboardingCard, SectionHeader, WarningCard } from '../components';
import { useFinancialDiagnosis, useFinancialProfile } from '../features/financial/hooks/useFinancial';
import { useRecommendations } from '../features/intelligence/hooks/useIntelligence';
import type { ApiErrorShape } from '../services/api';
import { formatCurrency } from '../utils/formatters';

const labels: Record<string, string> = { renda_fixa: 'Renda fixa', fii: 'FIIs', acoes: 'Ações', etf: 'ETFs', bdr: 'BDRs', cripto: 'Cripto' };

function isMissingProfile(error: unknown) {
  const apiError = error as ApiErrorShape | null;
  return Boolean(apiError && [400, 404, 422].includes(apiError.status));
}

function scoreContext(score: number) {
  if (score >= 75) return 'Boa base para planejar próximos aportes.';
  if (score >= 55) return 'Há espaço para fortalecer reserva e orçamento.';
  if (score > 0) return 'Prioridade deve ser estabilidade antes de risco.';
  return 'Complete seu perfil para calcular o score.';
}

export function DashboardPage() {
  const profile = useFinancialProfile();
  const diagnosis = useFinancialDiagnosis();
  const recommendations = useRecommendations();
  const missingProfile = isMissingProfile(profile.error) || isMissingProfile(diagnosis.error);
  const error = (!missingProfile ? (diagnosis.error || recommendations.error || profile.error) : null) as ApiErrorShape | null;
  const score = diagnosis.data?.score.score ?? 0;
  const warnings = [...(diagnosis.data?.score.recommendations ?? []), ...(recommendations.data?.warnings ?? [])];

  function refetchAll() {
    profile.refetch();
    diagnosis.refetch();
    recommendations.refetch();
  }

  return (
    <section className="vn-page">
      <SectionHeader
        eyebrow="Dashboard"
        title="Visão financeira objetiva, sem ruído."
        description="Resumo real do backend com score, capacidade de aporte, alocação educacional e alertas principais."
        action={<Button variant="secondary" onClick={refetchAll}>Atualizar contexto <ArrowUpRight size={16} /></Button>}
      />

      {profile.isLoading && <Card><LoadingState label="Verificando perfil financeiro..." /></Card>}
      {missingProfile && <OnboardingCard onCompleted={refetchAll} />}
      {!missingProfile && (diagnosis.isLoading || recommendations.isLoading) && <Card><LoadingState label="Carregando contexto financeiro real..." /></Card>}
      {error && <Card><ErrorState title="Não foi possível carregar o dashboard" description={error.message} action={<Button variant="secondary" onClick={refetchAll}>Tentar novamente</Button>} /></Card>}

      {!missingProfile && diagnosis.data && recommendations.data && (
        <>
          <div className="vn-metrics vn-metrics--refined">
            <MetricCard icon={<ShieldCheck size={20} />} label="Score financeiro" value={`${score}/100`} helper={scoreContext(score)} badge={diagnosis.data.score.level} tone={score >= 70 ? 'success' : 'warning'} />
            <MetricCard icon={<PiggyBank size={20} />} label="Capacidade de aporte" value={formatCurrency(diagnosis.data.budget.investment_capacity)} helper="Estimativa mensal calculada pelo diagnóstico." badge="mensal" />
            <MetricCard icon={<WalletCards size={20} />} label="Perfil ajustado" value={recommendations.data.adjusted_risk_profile} helper="Pode mudar por score, reserva ou restrição de risco." badge="educacional" tone="warning" />
          </div>

          <div className="vn-grid vn-grid--two vn-grid--dashboard">
            <AllocationCard labels={labels} items={recommendations.data.allocation} title="Alocação sugerida" description="Distribuição calculada pelo backend. Não representa ordem definitiva de compra." />
            <Card title="Leitura executiva" description="O que observar antes de avançar para ativos.">
              <div className="vn-insight-list">
                <WarningCard title="Score" description={scoreContext(score)} tone={score >= 70 ? 'success' : 'warning'} />
                <WarningCard title="Reserva" description={diagnosis.data.budget.emergency_reserve_priority ? 'A reserva ainda tem prioridade. O backend tende a reduzir ativos de risco.' : 'O diagnóstico não marcou prioridade crítica para reserva neste momento.'} tone={diagnosis.data.budget.emergency_reserve_priority ? 'warning' : 'success'} />
                <WarningCard title="Risco" description={diagnosis.data.budget.high_risk_allowed ? 'Ativos de maior risco podem aparecer com limites educacionais.' : 'Cripto e exposição agressiva podem ser bloqueadas pelo contexto financeiro.'} tone={diagnosis.data.budget.high_risk_allowed ? 'success' : 'warning'} />
              </div>
            </Card>
          </div>

          <Card title="Alertas financeiros" description="Avisos retornados pelas camadas financeira e de inteligência.">
            {warnings.length > 0 ? <div className="vn-warning-grid">{warnings.slice(0, 6).map((warning) => <WarningCard key={warning} description={warning} />)}</div> : <EmptyState title="Sem alertas críticos" description="O backend não retornou avisos para este contexto." />}
          </Card>
        </>
      )}
    </section>
  );
}
