import { Area, AreaChart, Bar, BarChart, CartesianGrid, Cell, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { ArrowUpRight, Banknote, Brain, Landmark, PiggyBank, ShieldCheck, Target, TrendingUp, Wallet } from 'lucide-react';
import { AlertCard, Button, Card, ChartCard, EmptyState, LoadingState, MetricCard, RecommendationCard, SectionHeader, StatusBadge } from '../components/ui';
import { useApi } from '../hooks/useApi';
import { Dashboard as DashboardType } from '../types/finance';
import { money, pct } from '../utils/format';

function AllocationPanel({ data }: { data: NonNullable<DashboardType['intelligent_allocation']> }) {
  return (
    <Card className="allocation-intelligence-card" interactive>
      <div className="card-title">
        <div>
          <span className="eyebrow">Vinance Intelligence</span>
          <h3>Quanto investir e onde alocar</h3>
          <p>{data.decision}</p>
        </div>
        <StatusBadge tone={data.can_invest ? 'good' : 'warn'}>{data.can_invest ? 'Pode investir' : 'Ajustar caixa'}</StatusBadge>
      </div>

      <div className="metrics-grid allocation-metrics">
        <MetricCard icon={<PiggyBank size={18} />} label="Investir agora" value={data.investable_amount} tone={data.can_invest ? 'good' : 'warn'} />
        <MetricCard icon={<Target size={18} />} label="Método recomendado" value={data.method.name} hint={data.method.reason} />
        <MetricCard icon={<ShieldCheck size={18} />} label="Perfil calculado" value={data.risk_profile} />
        <MetricCard icon={<Landmark size={18} />} label="Reserva alvo" value={data.emergency_reserve_target} hint={`Gap: ${money(data.emergency_reserve_gap)}`} />
      </div>

      <div className="grid two">
        <div className="quant-decision-box">
          <strong>Próxima ação</strong>
          <span>{data.next_action}</span>
          <small>Despesa/renda: {pct(data.expense_ratio_pct)}</small>
        </div>
        <div className="quant-decision-box">
          <strong>Distribuição do orçamento</strong>
          <span>{data.method.needs_pct}% necessidades · {data.method.wants_pct}% qualidade de vida · {data.method.investments_pct}% investimentos</span>
          <small>Baseado nas receitas e despesas cadastradas no mês.</small>
        </div>
      </div>

      {data.markets?.length ? (
        <div className="market-list" style={{ marginTop: 16 }}>
          {data.markets.map((m) => (
            <div className="market-row" key={`${m.name}-${m.market}`}>
              <div>
                <strong>{m.name}</strong>
                <small>{m.market} · risco {m.risk} · {m.reason}</small>
              </div>
              <div style={{ textAlign: 'right' }}>
                <strong>{m.allocation_pct}%</strong>
                <small>{money(m.amount)}</small>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <EmptyState title="Sem alocação por enquanto" message="Quando houver saldo investível, o Vinance mostrará automaticamente os mercados sugeridos." />
      )}

      <div className="advisor-notes">
        {data.advisor_notes?.map((note) => <span className="pill" key={note}>{note}</span>)}
      </div>
    </Card>
  );
}

export default function Dashboard() {
  const { data, isLoading, error } = useApi<DashboardType>(['dashboard'], '/dashboard');
  if (isLoading) return <div className="page"><LoadingState title="Montando sua visão executiva..." rows={5} /></div>;
  if (error || !data) return <div className="page"><EmptyState title="Dashboard pronto para começar" message="Cadastre receitas e despesas para liberar score, orçamento, diagnóstico e sugestão de investimento." /></div>;

  const m = data.metrics;
  const intelligence = data.intelligent_allocation;
  const budgetUsed = data.budget?.monthly_income ? Math.min(100, (data.budget.actual.expenses / data.budget.monthly_income) * 100) : 0;
  const insights = [
    { title: 'Orçamento usado', value: `${budgetUsed.toFixed(0)}%`, text: 'Acompanhe se o mês está dentro do plano.' },
    { title: 'Tendência financeira', value: m.monthly_balance >= 0 ? 'Positiva' : 'Atenção', text: m.monthly_balance >= 0 ? 'Há sobra disponível para metas e aportes.' : 'Revise categorias com maior consumo.' },
    { title: 'Próximo aporte', value: intelligence ? money(intelligence.investable_amount) : money(data.recommendation.amount), text: intelligence?.next_action || 'Sugestão automática baseada no orçamento.' },
  ];

  return (
    <div className="page">
      <SectionHeader
        eyebrow="Visão executiva"
        title="Dashboard Financeiro"
        description="Receitas, despesas e inteligência de alocação conectadas para responder quanto investir e onde alocar."
        action={<div className="score-pill">Score {m.financial_score}</div>}
      />

      <div className="hero-summary">
        <section className="premium-card hero-balance">
          <span className="eyebrow">Saldo do mês</span>
          <strong>{money(m.monthly_balance)}</strong>
          <p>{m.monthly_balance >= 0 ? 'Seu mês está com sobra. O Vinance transforma esse saldo em plano de investimento.' : 'Seu mês está pressionado. O Vinance prioriza correção de caixa antes de sugerir risco.'}</p>
          <div className="progress-track"><span className="progress-value" style={{ width: `${budgetUsed}%` }} /></div>
          <small>Orçamento utilizado: {budgetUsed.toFixed(0)}%</small>
        </section>
        <section className="premium-card insight-list">
          <span className="eyebrow">Resumo inteligente</span>
          {insights.map((i) => <div className="insight-item" key={i.title}><div className="metric-icon"><ArrowUpRight size={17} /></div><div><strong>{i.title}: {i.value}</strong><p>{i.text}</p></div></div>)}
        </section>
      </div>

      <div className="metrics-grid">
        <MetricCard icon={<Wallet size={18} />} label="Receitas" value={m.total_income} />
        <MetricCard icon={<TrendingUp size={18} />} label="Despesas" value={m.total_expenses} tone="warn" />
        <MetricCard icon={<Banknote size={18} />} label="Saldo livre" value={m.available_to_invest} tone="good" />
        <MetricCard icon={<Brain size={18} />} label="% investido" value={pct(m.invested_pct)} hint={money(m.realized_investment)} />
      </div>

      {intelligence && <AllocationPanel data={intelligence} />}

      <RecommendationCard title={data.recommendation.title} message={data.recommendation.message} amount={data.recommendation.amount} />

      <div className="grid two">
        <ChartCard title="Evolução mensal" hint="Receitas x despesas">
          <ResponsiveContainer width="100%" height={300}>
            <AreaChart data={data.charts.evolution}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="month" />
              <YAxis tickFormatter={(v) => `R$ ${Number(v) / 1000}k`} />
              <Tooltip formatter={(v) => money(Number(v))} />
              <Area type="monotone" dataKey="receitas" stroke="currentColor" fill="currentColor" fillOpacity={0.16} strokeWidth={3} />
              <Area type="monotone" dataKey="despesas" stroke="currentColor" fill="currentColor" fillOpacity={0.08} strokeWidth={2} />
            </AreaChart>
          </ResponsiveContainer>
        </ChartCard>
        <ChartCard title="Gastos por categoria" hint="Onde o dinheiro saiu">
          {data.charts.by_category.length ? <ResponsiveContainer width="100%" height={300}><PieChart><Pie data={data.charts.by_category} dataKey="value" nameKey="name" outerRadius={108} innerRadius={58} paddingAngle={3} label>{data.charts.by_category.map((_, i) => <Cell key={i} />)}</Pie><Tooltip formatter={(v) => money(Number(v))} /></PieChart></ResponsiveContainer> : <EmptyState title="Sem despesas no mês" message="Cadastre despesas para visualizar categorias." />}
        </ChartCard>
      </div>

      <ChartCard title="Comparativo mensal rápido">
        <ResponsiveContainer width="100%" height={260}>
          <BarChart data={data.charts.evolution}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="month" />
            <Tooltip formatter={(v) => money(Number(v))} />
            <Bar dataKey="receitas" radius={[10, 10, 0, 0]} fill="currentColor" />
            <Bar dataKey="despesas" radius={[10, 10, 0, 0]} fill="currentColor" opacity={0.45} />
          </BarChart>
        </ResponsiveContainer>
      </ChartCard>

      <div className="grid three">{data.alerts.map((a) => <AlertCard key={a.title} title={a.title} message={a.message} tone={a.severity} />)}</div>
    </div>
  );
}
