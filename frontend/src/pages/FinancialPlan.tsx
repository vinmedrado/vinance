import {useQuery} from '@tanstack/react-query';
import {api} from '../services/api';
import {AlertTriangle, CheckCircle2, LineChart, PiggyBank, Sparkles, Target, TrendingUp, Wallet} from 'lucide-react';

function money(value:number){return new Intl.NumberFormat('pt-BR',{style:'currency',currency:'BRL'}).format(value||0)}
function pct(value:number){return `${Math.round(value||0)}%`}

export default function FinancialPlan(){
  const {data,isLoading,error}=useQuery({queryKey:['ai-financial-advisor'],queryFn:async()=>{const {data}=await api.get('/intelligence/ai-financial-advisor');return data}});
  if(isLoading)return <section className="page"><div className="premium-card"><p>Atualizando seu assistente financeiro inteligente...</p></div></section>;
  if(error)return <section className="page"><div className="premium-card"><h2>Meu Plano Financeiro</h2><p>Não foi possível carregar seu plano agora. Verifique login, renda e despesas cadastradas.</p></div></section>;
  const advisor=data.decision_advisor||{};
  const budgetAdvisor=data.adaptive_model?.advisor||{};
  const summary=budgetAdvisor.input_summary||{};
  const limits=budgetAdvisor.suggested_limits||{};
  const health=data.health||{};
  const coaching=data.coaching||{messages:[],tips:[],alerts:[]};
  const forecast=data.forecast||{scenarios:[]};
  const timeline=data.timeline||{events:[]};
  const behavior=data.behavioral_intelligence||{signals:[],plain_language_summary:""};
  const memory=data.memory||{patterns:[],insights:[],critical_categories:[]};
  const retention=data.retention||{milestones:[],progress_summary:""};
  const baseScenario=forecast.scenarios?.find((s:any)=>s.name==='base')||forecast.scenarios?.[0]||{};
  return <section className="page">
    <div className="hero-card premium-card">
      <span className="eyebrow">Meu Plano Financeiro Evolutivo</span>
      <h1>{data.advisor_main_message}</h1>
      <p>{advisor.recommendation}</p>
      <div className="hero-actions"><span className="pill">Advisor: {advisor.title}</span><span className="pill">Fase: {health.financial_phase}</span><span className="pill">Memória: {memory.trend}</span></div>
    </div>

    <div className="kpi-grid metrics-grid">
      <div className="kpi metric-card"><Wallet size={20}/><span>Renda</span><strong>{money(summary.monthly_income)}</strong></div>
      <div className="kpi metric-card"><AlertTriangle size={20}/><span>Despesas</span><strong>{money(summary.total_expenses)}</strong></div>
      <div className="kpi metric-card"><PiggyBank size={20}/><span>Sobra segura</span><strong>{money(budgetAdvisor.investment_capacity)}</strong></div>
      <div className="kpi metric-card"><Sparkles size={20}/><span>Score financeiro</span><strong>{health.health_score}/100</strong></div>
    </div>

    <div className="grid two">
      <div className="premium-card">
        <h2>O que eu preciso fazer agora?</h2>
        <p>{data.next_best_action}</p>
        <ul className="clean-list">{coaching.tips?.slice(0,5).map((item:string)=><li key={item}><CheckCircle2 size={16}/> {item}</li>)}</ul>
      </div>
      <div className="premium-card">
        <h2>Coaching do mês</h2>
        <ul className="clean-list">{coaching.messages?.map((item:string)=><li key={item}><Sparkles size={16}/> {item}</li>)}</ul>
      </div>
    </div>

    <div className="grid two">
      <div className="premium-card">
        <h2>Limites sugeridos</h2>
        <ul className="clean-list">
          <li>Necessidades: <strong>{money(limits.needs)}</strong></li>
          <li>Desejos/lazer: <strong>{money(limits.wants)}</strong></li>
          <li>Dívidas/contas: <strong>{money(limits.debts)}</strong></li>
          <li>Reserva: <strong>{money(limits.emergency_reserve)}</strong></li>
          <li>Investimentos: <strong>{money(budgetAdvisor.investment_capacity)}</strong></li>
        </ul>
      </div>
      <div className="premium-card">
        <h2>Previsão financeira</h2>
        <p>{forecast.plain_language_summary}</p>
        <p>No cenário base, o patrimônio projetado em 12 meses é de <strong>{money(baseScenario.projected_net_worth)}</strong>.</p>
        <div className="budget-bars">{forecast.scenarios?.map((s:any)=><p key={s.name}>{s.name}: <strong>{money(s.projected_net_worth)}</strong><div><span style={{width:`${Math.min(100,(s.projected_net_worth||0)/Math.max(1,baseScenario.projected_net_worth||1)*75)}%`}} /></div></p>)}</div>
      </div>
    </div>

    <div className="grid two">
      <div className="premium-card">
        <h2>Comportamento financeiro</h2>
        <p>Disciplina: <strong>{behavior.discipline_score}/100</strong> · estabilidade {behavior.stability_score}/100</p>
        <ul className="clean-list">{memory.insights?.map((i:string)=><li key={i}><TrendingUp size={16}/> {i}</li>)}</ul>
      </div>
      <div className="premium-card">
        <h2>Jornada financeira</h2>
        <ul className="clean-list timeline-list">{timeline.events?.slice(0,6).map((ev:any,idx:number)=><li key={`${ev.period}-${idx}`}><LineChart size={16}/><span><strong>{ev.title}</strong><br/><small>{ev.period} — {ev.description}</small></span></li>)}</ul>
      </div>
    </div>

    <div className="grid two">
      <div className="premium-card">
        <h2>Memória financeira</h2>
        <p>{memory.memory_strength} · {memory.patterns?.join(' · ')}</p>
        <ul className="clean-list">{memory.critical_categories?.slice(0,3).map((c:any)=><li key={c.category}><Target size={16}/> {c.category}: {money(c.total)}</li>)}</ul>
      </div>
      <div className="premium-card">
        <h2>Marcos de evolução</h2>
        <p>{retention.progress_summary}</p>
        <ul className="clean-list">{retention.milestones?.slice(0,3).map((m:any)=><li key={m.title}><CheckCircle2 size={16}/> {m.title}</li>)}</ul>
      </div>
    </div>

    {coaching.alerts?.length>0&&<div className="premium-card warning"><h2>Alertas inteligentes</h2><ul>{coaching.alerts.map((a:any)=><li key={a.message}><strong>{a.severity}</strong>: {a.message}</li>)}</ul></div>}

    <div className="premium-card">
      <h2>Investimentos acompanham sua saúde financeira</h2>
      <p>{advisor.recommendation}</p>
      <div className="hero-actions"><a className="button" href="/despesas">Cadastrar despesa</a><a className="button secondary" href="/orcamento">Revisar orçamento</a><a className="button secondary" href="/metas">Ajustar meta</a><a className="button secondary" href="/investimentos">Ver investimentos</a></div>
    </div>
    <p className="muted">{data.disclaimer}</p>
  </section>
}
