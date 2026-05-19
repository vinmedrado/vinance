import { useMemo, useState } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import { Activity, AlertTriangle, BrainCircuit, ChartNoAxesCombined, CircleDollarSign, LineChart as LineIcon, Play, Radar, ShieldCheck, Sparkles, Target } from 'lucide-react';
import { Area, AreaChart, CartesianGrid, Cell, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { getQuantHealth, getQuantMarkets, getQuantRuns, runInvestmentDecision, runQuantBacktest, syncQuantMarketData, trainQuantModel, type RiskProfile } from '../services/quant';
import { money } from '../utils/format';

const pct = (value?: number) => `${(((value ?? 0) * 100)).toFixed(1)}%`;
const number = (value?: number) => Number(value ?? 0).toLocaleString('pt-BR');

const profiles: RiskProfile[] = ['conservador', 'moderado', 'arrojado', 'agressivo'];

const bucketLabel: Record<string, string> = {
  reserva_liquidez: 'Reserva e liquidez',
  renda_fixa: 'Renda fixa',
  fundos_imobiliarios: 'FIIs',
  acoes_etfs: 'Ações e ETFs',
  internacional: 'Internacional',
  cripto: 'Cripto controlado',
};

export default function QuantLab() {
  const [riskProfile, setRiskProfile] = useState<RiskProfile>('moderado');
  const [income, setIncome] = useState(8500);
  const [expenses, setExpenses] = useState(5200);
  const [cash, setCash] = useState(30000);
  const [reserve, setReserve] = useState(18000);
  const [ticker, setTicker] = useState('BOVA11');

  const health = useQuery({ queryKey: ['quant-health'], queryFn: getQuantHealth, refetchInterval: 30000 });
  const markets = useQuery({ queryKey: ['quant-markets'], queryFn: getQuantMarkets });
  const runs = useQuery({ queryKey: ['quant-runs'], queryFn: getQuantRuns, refetchOnWindowFocus: false, refetchInterval: 45000 });

  const decision = useMutation({
    mutationFn: () => runInvestmentDecision({
      monthly_income: income,
      monthly_expenses: expenses,
      cash_available: cash,
      emergency_reserve_current: reserve,
      risk_profile: riskProfile,
      horizon_months: 36,
      objective: 'crescimento patrimonial com controle de risco',
    }),
    onSuccess: () => runs.refetch(),
  });

  const backtest = useMutation({
    mutationFn: () => runQuantBacktest({
      ticker,
      initial_capital: Math.max(10000, cash),
      monthly_contribution: Math.max(0, income - expenses) * 0.55,
      strategy: 'momentum_quality_risk_control',
      horizon_months: 48,
      risk_profile: riskProfile,
    }),
    onSuccess: () => runs.refetch(),
  });

  const model = useMutation({
    mutationFn: () => trainQuantModel({ market: 'todos', risk_profile: riskProfile, horizon_months: 36, capital: cash }),
    onSuccess: () => runs.refetch(),
  });

  const syncMarketData = useMutation({
    mutationFn: syncQuantMarketData,
    onSuccess: () => { markets.refetch(); health.refetch(); runs.refetch(); },
  });

  const lastDecision = decision.data;
  const lastBacktest = backtest.data;
  const lastModel = model.data;
  const marketItems = markets.data?.items ?? [];
  const topMarkets = lastDecision?.top_opportunities ?? marketItems.slice(0, 8);
  const allocation = lastDecision?.allocation ?? [];
  const investable = lastDecision?.investable_capital ?? Math.max(cash - Math.max(expenses * 6 - reserve, 0), 0);
  const surplus = Math.max(income - expenses, 0);

  const pieData = useMemo(() => allocation.map((a: any) => ({ name: bucketLabel[a.bucket] ?? a.bucket, value: Math.round((a.weight ?? 0) * 100), amount: a.amount })), [allocation]);

  return (
    <div className="page quant-page">
      <div className="page-header">
        <div>
          <span className="eyebrow">Vinance Quant Intelligence</span>
          <h1>Centro de decisão para investir com IA.</h1>
          <p>O Vinance cruza fluxo de caixa, reserva, risco, mercados e simulações para dizer quando investir, quanto alocar e quais mercados priorizar.</p>
        </div>
        <div className="score-circle"><div>{Math.round((lastModel?.metrics?.confidence ?? 0.72) * 100)}<small>IQ</small></div><span style={{fontSize:11, color:'var(--muted)'}}>runs {(health.data?.tables?.decisions ?? 0) + (health.data?.tables?.backtests ?? 0)}</span></div>
      </div>

      <section className="premium-card hero-card quant-hero-card">
        <div className="quant-control-grid">
          <label>Renda mensal<input type="number" value={income} onChange={(e) => setIncome(Number(e.target.value))} /></label>
          <label>Despesas mensais<input type="number" value={expenses} onChange={(e) => setExpenses(Number(e.target.value))} /></label>
          <label>Caixa disponível<input type="number" value={cash} onChange={(e) => setCash(Number(e.target.value))} /></label>
          <label>Reserva atual<input type="number" value={reserve} onChange={(e) => setReserve(Number(e.target.value))} /></label>
          <label>Perfil de risco<select value={riskProfile} onChange={(e) => setRiskProfile(e.target.value as RiskProfile)}>{profiles.map((p) => <option key={p}>{p}</option>)}</select></label>
          <label>Ativo do backtest<select value={ticker} onChange={(e) => setTicker(e.target.value)}>{['BOVA11','IVVB11','SMAL11','HGLG11','ITUB4','WEGE3','PETR4','HASH11'].map((t) => <option key={t}>{t}</option>)}</select></label>
        </div>
        <div className="hero-actions">
          <button className="btn btn-primary" disabled={decision.isPending} onClick={() => decision.mutate()}><Sparkles size={18}/> Calcular capital investível</button>
          <button className="btn btn-soft" disabled={backtest.isPending} onClick={() => backtest.mutate()}><Play size={18}/> Rodar backtest</button>
          <button className="btn btn-ghost" disabled={model.isPending} onClick={() => model.mutate()}><BrainCircuit size={18}/> Treinar IA</button>
          <button className="btn btn-ghost" disabled={syncMarketData.isPending} onClick={() => syncMarketData.mutate()}><Activity size={18}/> Sincronizar universo</button>
        </div>
      </section>

      <section className="metrics-grid">
        <div className="premium-card metric-card tone-success"><div className="metric-top"><span>Capital investível</span><CircleDollarSign className="metric-icon" size={18}/></div><strong>{money(investable)}</strong><small>após reserva e fluxo mensal</small></div>
        <div className="premium-card metric-card"><div className="metric-top"><span>Sobra mensal</span><Activity className="metric-icon" size={18}/></div><strong>{money(surplus)}</strong><small>capacidade recorrente</small></div>
        <div className="premium-card metric-card tone-warn"><div className="metric-top"><span>Drawdown simulado</span><AlertTriangle className="metric-icon" size={18}/></div><strong>{pct(lastBacktest?.max_drawdown ?? 0.118)}</strong><small>risco máximo estimado</small></div>
        <div className="premium-card metric-card tone-good"><div className="metric-top"><span>Confiança IA</span><ShieldCheck className="metric-icon" size={18}/></div><strong>{pct(lastModel?.metrics?.confidence ?? 0.72)}</strong><small>sinais do modelo</small></div>
      </section>

      <section className="grid two quant-main-grid">
        <div className="premium-card chart-card">
          <div className="card-title"><div><h2>Quando investir</h2><p>{lastDecision?.decision ?? 'Execute a análise para gerar uma decisão contextual com base nos seus dados.'}</p></div><Target color="var(--cyan)"/></div>
          <div className="quant-decision-box">
            <strong>{lastDecision?.status ?? 'aguardando análise'}</strong>
            <span>Reserva alvo: {money(lastDecision?.reserve_target ?? expenses * 6)}</span>
            <span>Gap de reserva: {money(lastDecision?.reserve_gap ?? Math.max(expenses * 6 - reserve, 0))}</span>
            <span>Aporte mensal recomendado: {money(lastDecision?.monthly_investable ?? surplus * .55)}</span>
          </div>
          <ul className="clean-list" style={{ marginTop: 16 }}>
            {(lastDecision?.risk_controls ?? ['Preserve liquidez antes de risco.', 'Diversifique por classe de ativo.', 'Rebalanceie mensalmente.']).map((r: string) => <li key={r}><ShieldCheck size={16} color="var(--cyan)"/> {r}</li>)}
          </ul>
        </div>

        <div className="premium-card chart-card">
          <div className="card-title"><div><h2>Alocação recomendada</h2><p>Distribuição sugerida por classe e perfil de risco.</p></div><Radar color="var(--cyan)"/></div>
          <div style={{ height: 280 }}>
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie data={pieData.length ? pieData : [{ name: 'Renda fixa', value: 45 }, { name: 'Ações e ETFs', value: 30 }, { name: 'FIIs', value: 15 }, { name: 'Internacional', value: 10 }]} dataKey="value" nameKey="name" innerRadius={65} outerRadius={105} paddingAngle={4}>
                  {(pieData.length ? pieData : [1,2,3,4]).map((_: any, i: number) => <Cell key={i} />)}
                </Pie>
                <Tooltip formatter={(value: any, name: any, props: any) => [`${value}% ${props?.payload?.amount ? '• ' + money(props.payload.amount) : ''}`, name]} />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </div>
      </section>

      <section className="grid two">
        <div className="premium-card chart-card">
          <div className="card-title"><div><h2>Backtest</h2><p>{lastBacktest?.interpretation ?? 'Rode uma simulação para comparar retorno e risco.'}</p></div><LineIcon color="var(--cyan)"/></div>
          <div style={{ height: 320 }}>
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={lastBacktest?.equity_curve ?? []}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="month" />
                <YAxis />
                <Tooltip formatter={(value: any) => money(Number(value))} />
                <Area type="monotone" dataKey="equity" stroke="currentColor" fillOpacity={0.18} fill="currentColor" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
          <div className="kpi-grid">
            <div className="pill">Retorno {pct(lastBacktest?.total_return)}</div>
            <div className="pill">Sharpe-like {number(lastBacktest?.sharpe_like)}</div>
            <div className="pill">Win rate {pct(lastBacktest?.win_rate)}</div>
            <div className="pill">Final {money(lastBacktest?.final_capital ?? 0)}</div>
          </div>
        </div>

        <div className="premium-card chart-card">
          <div className="card-title"><div><h2>Mercados para alocar</h2><p>Ranking calculado por risco, liquidez, retorno esperado e cenário macro.</p></div><ChartNoAxesCombined color="var(--cyan)"/></div>
          <div className="market-list">
            {topMarkets.slice(0, 8).map((m: any) => (
              <div className="market-row" key={m.ticker}>
                <div><strong>{m.ticker}</strong><small>{m.name} • {m.market}</small></div>
                <span className="badge badge-info">Score {Math.round(m.score ?? m.macro_score ?? 0)}</span>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="grid two">
        <div className="premium-card">
          <div className="card-title"><div><h2>Modelo IA</h2><p>Treinamento contextual para priorizar sinais por mercado.</p></div><BrainCircuit color="var(--cyan)"/></div>
          <div className="metrics-grid" style={{ gridTemplateColumns: 'repeat(4,minmax(0,1fr))' }}>
            <div className="pill">AUC {number(lastModel?.metrics?.auc)}</div>
            <div className="pill">Precision {number(lastModel?.metrics?.precision)}</div>
            <div className="pill">Recall {number(lastModel?.metrics?.recall)}</div>
            <div className="pill">Confiança {pct(lastModel?.metrics?.confidence)}</div>
          </div>
          <div className="market-list">
            {(lastModel?.signals ?? []).slice(0, 7).map((s: any) => <div className="market-row" key={s.ticker}><div><strong>{s.ticker}</strong><small>{s.name}</small></div><span className={`badge ${s.signal === 'comprar' ? 'badge-good' : s.signal === 'evitar' ? 'badge-danger' : 'badge-warn'}`}>{s.signal} • {pct(s.probability)}</span></div>)}
          </div>
        </div>

        <div className="premium-card">
          <div className="card-title"><div><h2>Histórico operacional</h2><p>Últimas decisões e backtests persistidos.</p></div></div>
          <div className="market-list">
            {(runs.data?.decisions ?? []).slice(0, 4).map((r: any) => <div className="market-row" key={`d-${r.id}`}><div><strong>Decisão #{r.id}</strong><small>{r.risk_profile} • {r.decision}</small></div><span className="badge badge-info">{money(r.investable_capital)}</span></div>)}
            {(runs.data?.backtests ?? []).slice(0, 4).map((r: any) => <div className="market-row" key={`b-${r.id}`}><div><strong>Backtest {r.ticker}</strong><small>{r.strategy}</small></div><span className="badge badge-good">{pct(r.total_return)}</span></div>)}
            {(runs.data?.trainings ?? []).slice(0, 3).map((r: any) => <div className="market-row" key={`t-${r.id}`}><div><strong>Treino IA #{r.id}</strong><small>{r.market} • {r.risk_profile}</small></div><span className="badge badge-info">AUC {number(r.auc)}</span></div>)}
            {(runs.data?.jobs ?? []).slice(0, 3).map((r: any) => <div className="market-row" key={`j-${r.id}`}><div><strong>Job {r.job_type}</strong><small>{r.id}</small></div><span className="badge badge-warn">{r.status}</span></div>)}
          </div>
        </div>
      </section>
    </div>
  );
}
