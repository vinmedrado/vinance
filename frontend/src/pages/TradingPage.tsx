import { useEffect, useMemo, useState, type ReactNode } from 'react';
import { Activity, AlertTriangle, Clock3, FlaskConical, ShieldCheck } from 'lucide-react';
import { Badge, Button, Card, EmptyState, ErrorState, Input, LoadingState, Modal, SectionHeader, Tabs } from '../components';
import { useHouseholdDefault, useHouseholdList } from '../features/household/hooks/useHousehold';
import {
  usePaperEvents,
  usePaperOrders,
  usePaperPositions,
  useTradingBacktests,
  useTradingModels,
  useTradingMutations,
  useTradingOpportunities,
  useTradingOverview,
} from '../features/trading/hooks/useTrading';
import type { TradingOpportunity } from '../features/trading/types/trading.types';
import type { ApiErrorShape } from '../services/api';
import { formatDateTime, formatRatioAsPercent } from '../utils/formatters';

type TabId = 'overview' | 'opportunities' | 'paper' | 'backtests' | 'models' | 'history';

const statusLabels: Record<string, string> = {
  NOT_PAPER_READY: 'Modelos ainda não liberados', PAPER_READY: 'Apto para simulação',
  PAPER_ACTIVE: 'Paper ativo', PAPER_CANDIDATE: 'Candidato a Paper', VALIDATED: 'Validado',
  RESEARCH: 'Pesquisa', REJECTED: 'Reprovado', RETIRED: 'Retirado',
  FILLED: 'Executada na simulação', PENDING: 'Pendente', CANCELLED: 'Cancelada',
  OPEN: 'Aberta', CLOSED: 'Fechada',
};

const reasonLabels: Record<string, string> = {
  REAL_TRADING_NOT_SUPPORTED: 'Trading real não é suportado.',
  SPECULATIVE_CAPITAL_NOT_AUTHORIZED: 'Nenhum capital real foi autorizado para risco.',
  TRADING_DISPATCH_DISABLED: 'O Autopilot não envia capital para Trading.',
  PRIORITY_DEBT: 'Há dívida prioritária no contexto financeiro.',
  EMERGENCY_RESERVE_ABSENT: 'A reserva de emergência ainda precisa ser formada.',
  EMERGENCY_RESERVE_BUILDING: 'A reserva de emergência está em formação.',
  EMERGENCY_RESERVE_UNKNOWN: 'Ainda faltam dados sobre a reserva de emergência.',
};

function virtualMoney(value: string | number | null | undefined) {
  const number = Number(value);
  return Number.isFinite(number)
    ? `${new Intl.NumberFormat('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(number)} USDT`
    : '—';
}

function actionKey(prefix: string) {
  const id = globalThis.crypto?.randomUUID?.() ?? `${Date.now()}-${Math.random().toString(16).slice(2)}`;
  return `${prefix}:${id}`;
}

function QueryState({ query, children }: { query: { isLoading: boolean; error: unknown }; children: ReactNode }) {
  if (query.isLoading) return <Card><LoadingState label="Consultando o Trading simulado…" /></Card>;
  if (query.error) return <Card><ErrorState title="Trading indisponível" description={(query.error as ApiErrorShape).message ?? 'Não foi possível consultar esta área.'} /></Card>;
  return <>{children}</>;
}

function TradingSummary({ householdId }: { householdId: number | null }) {
  const overview = useTradingOverview(householdId);
  const mutations = useTradingMutations();
  const modelReady = overview.data?.models.paper_trading_ready === true;
  const opportunities = Number(overview.data?.counts.opportunities ?? 0);
  return <QueryState query={overview}>{overview.data && (
    <div className="vn-trading-stack">
      <div className="vn-trading-status-line">
        <div><span>Sistema</span><strong>Disponível para simulação</strong></div>
        <div><span>Modelo validado</span><strong>{modelReady ? 'Sim' : 'Não'}</strong></div>
        <div><span>Oportunidades atuais</span><strong>{opportunities}</strong></div>
      </div>
      {!modelReady && <div className="vn-trading-readiness"><AlertTriangle size={18} /><div><strong>Nenhum modelo aprovado para oportunidades Paper neste momento.</strong><p>A API e a conta virtual continuam disponíveis, mas novas operações permanecem bloqueadas pela validação.</p></div></div>}
      {!overview.data.paper_account ? (
        <Card title="Criar conta de simulação" description="O saldo é inteiramente virtual, pessoal e separado do seu patrimônio.">
          <p className="vn-trading-note"><ShieldCheck size={18} /> Saldo inicial: 10.000 USDT virtuais. Nenhum dinheiro ou ativo real será movimentado.</p>
          <Button disabled={mutations.createAccount.isPending} onClick={() => mutations.createAccount.mutate()}>{mutations.createAccount.isPending ? 'Criando…' : 'Criar conta Paper'}</Button>
        </Card>
      ) : (
        <div className="vn-trading-metrics">
          <Card><span>Saldo virtual</span><strong>{virtualMoney(overview.data.paper_account.cash)}</strong></Card>
          <Card><span>Equity virtual</span><strong>{virtualMoney(overview.data.paper_account.equity)}</strong></Card>
          <Card><span>P&amp;L realizado</span><strong>{virtualMoney(overview.data.paper_account.realized_pnl)}</strong></Card>
          <Card><span>Drawdown máximo</span><strong>{formatRatioAsPercent(overview.data.paper_account.max_drawdown)}</strong></Card>
        </div>
      )}
      <Card title="Contexto financeiro" description="O Vinance apenas lê esse contexto. O saldo virtual não deriva da sua reserva ou dos seus investimentos.">
        <div className="vn-trading-risk-grid">
          <div><span>Simulação</span><strong>{overview.data.risk_budget.paper_simulation_allowed ? 'Permitida' : 'Bloqueada'}</strong></div>
          <div><span>Trading real</span><strong>Bloqueado</strong></div>
          <div><span>Capital real autorizado</span><strong>R$ 0,00</strong></div>
          <div><span>Escopo</span><strong>Pessoal</strong></div>
        </div>
        <ul className="vn-trading-reasons">{overview.data.risk_budget.blocking_reasons.map((reason) => <li key={reason}>{reasonLabels[reason] ?? reason.replace(/_/g, ' ').toLocaleLowerCase('pt-BR')}</li>)}</ul>
      </Card>
    </div>
  )}</QueryState>;
}

function Opportunities({ householdId }: { householdId: number | null }) {
  const query = useTradingOpportunities(true);
  const mutations = useTradingMutations();
  const [selected, setSelected] = useState<TradingOpportunity | null>(null);
  const [notional, setNotional] = useState('100');
  function submit() {
    if (!selected || householdId === null) return;
    mutations.createOrder.mutate({ householdId, payload: {
      idempotency_key: actionKey('paper-buy'), signal_id: selected.signal_id,
      symbol: selected.symbol, market: 'CRYPTO', interval: selected.interval,
      side: 'BUY', order_type: 'MARKET', notional, paper_only: true,
    } }, { onSuccess: () => setSelected(null) });
  }
  return <QueryState query={query}>{query.data?.items.length ? <>
    <div className="vn-trading-list">{query.data.items.map((item) => <Card key={item.signal_id} className="vn-trading-row">
      <div><strong>{item.symbol}</strong><span>{item.interval} · {formatDateTime(item.signal_time)}</span></div>
      <div><span>Confiança do modelo</span><strong>{item.confidence === null ? 'Não informada' : formatRatioAsPercent(item.confidence)}</strong></div>
      <div><span>Referência</span><strong>{virtualMoney(item.reference_price)}</strong></div>
      <div><Badge tone="warning">Oportunidade Paper</Badge><Button onClick={() => setSelected(item)}>Ver e simular</Button></div>
    </Card>)}</div>
    <Modal open={selected !== null} title={selected ? `Simular operação — ${selected.symbol}` : 'Simular operação'} onClose={() => setSelected(null)}>
      {selected && <div className="vn-trading-order-form">
        <p><strong>Simulação.</strong> Nenhuma ordem real será executada.</p>
        <dl><div><dt>Preço de referência</dt><dd>{virtualMoney(selected.reference_price)}</dd></div><div><dt>Stop do modelo</dt><dd>{virtualMoney(selected.stop_price)}</dd></div><div><dt>Alvo do modelo</dt><dd>{virtualMoney(selected.target_price)}</dd></div></dl>
        <Input label="Valor virtual (USDT)" type="number" min="1" step="0.01" value={notional} onChange={(event) => setNotional(event.target.value)} />
        <Button disabled={mutations.createOrder.isPending || householdId === null} onClick={submit}>{mutations.createOrder.isPending ? 'Simulando…' : 'Simular compra'}</Button>
      </div>}
    </Modal>
  </> : <Card><EmptyState title="Nenhuma oportunidade validada neste momento" description="Somente sinais atuais de modelos validados e promovidos para Paper aparecem aqui." /></Card>}</QueryState>;
}

function PaperPortfolio() {
  const orders = usePaperOrders(true);
  const positions = usePaperPositions(true);
  const mutations = useTradingMutations();
  return <div className="vn-trading-stack">
    <QueryState query={positions}><Card title="Posições simuladas" description="Posições pessoais e inteiramente virtuais.">
      {positions.data?.items.length ? <div className="vn-trading-list">{positions.data.items.map((item) => <div className="vn-trading-compact-row" key={item.id}>
        <div><strong>{item.symbol}</strong><span>{statusLabels[item.status] ?? item.status} · {formatDateTime(item.opened_at)}</span></div>
        <div><span>P&amp;L não realizado</span><strong>{virtualMoney(item.unrealized_pnl)}</strong></div>
        {item.status === 'OPEN' && <Button variant="secondary" disabled={mutations.closePosition.isPending} onClick={() => mutations.closePosition.mutate({ positionId: item.id, idempotencyKey: actionKey('paper-close') })}>Fechar posição simulada</Button>}
      </div>)}</div> : <EmptyState title="Nenhuma posição simulada" description="Uma posição aparecerá após uma oportunidade validada ser simulada." />}
    </Card></QueryState>
    <QueryState query={orders}><Card title="Ordens simuladas">
      {orders.data?.items.length ? <div className="vn-trading-list">{orders.data.items.map((item) => <div className="vn-trading-compact-row" key={item.id}>
        <div><strong>{item.symbol}</strong><span>{statusLabels[item.status] ?? item.status} · {formatDateTime(item.created_at)}</span></div>
        <div><span>Valor virtual</span><strong>{virtualMoney(item.notional)}</strong></div>
        {item.status === 'PENDING' && <Button variant="ghost" disabled={mutations.cancelOrder.isPending} onClick={() => mutations.cancelOrder.mutate({ orderId: item.id, idempotencyKey: actionKey('paper-cancel') })}>Cancelar ordem simulada</Button>}
      </div>)}</div> : <EmptyState title="Nenhuma ordem simulada" description="O histórico de ordens Paper aparecerá aqui." />}
    </Card></QueryState>
  </div>;
}

function Backtests() {
  const query = useTradingBacktests(true);
  return <QueryState query={query}>{query.data?.items.length ? <div className="vn-trading-list">{query.data.items.map((item) => <Card key={item.id} title={item.name} description={[item.symbol, item.interval].filter(Boolean).join(' · ')}>
    <div className="vn-trading-risk-grid"><div><span>Operações</span><strong>{item.trades ?? '—'}</strong></div><div><span>Retorno líquido</span><strong>{item.net_return === null ? '—' : formatRatioAsPercent(item.net_return)}</strong></div><div><span>Win rate</span><strong>{item.win_rate === null ? '—' : formatRatioAsPercent(item.win_rate)}</strong></div><div><span>Drawdown máximo</span><strong>{item.max_drawdown === null ? '—' : formatRatioAsPercent(item.max_drawdown)}</strong></div></div>
    <p className="vn-trading-note"><AlertTriangle size={17} /> {item.costs_modeled ? 'Custos e slippage foram modelados.' : 'Este backtest não comprova custos e slippage.'}</p>
  </Card>)}</div> : <Card><EmptyState title="Nenhum backtest publicado" description="Somente execuções válidas, com métricas persistidas, são exibidas." /></Card>}</QueryState>;
}

function Models() {
  const query = useTradingModels(true);
  return <QueryState query={query}>{query.data?.items.length ? <div className="vn-trading-list">{query.data.items.map((item) => <Card key={item.model_id} className="vn-trading-row">
    <div><strong>{item.symbol}</strong><span>{item.interval} · versão {item.version}</span></div><div><span>Validação</span><strong>{statusLabels[item.validation_status] ?? item.validation_status}</strong></div><div><span>Promoção</span><strong>{statusLabels[item.promotion_status] ?? item.promotion_status}</strong></div><div><Badge tone={item.promotion_status === 'PAPER_ACTIVE' ? 'success' : 'warning'}>{statusLabels[item.promotion_status] ?? item.promotion_status}</Badge></div>
  </Card>)}</div> : <Card><EmptyState title="Nenhum modelo promovido" description="Os artefatos de pesquisa não entram automaticamente no produto. Validation V2 ainda não autorizou um modelo Paper ativo." /></Card>}</QueryState>;
}

function Events() {
  const query = usePaperEvents(true);
  const eventLabels: Record<string, string> = { PAPER_ACCOUNT_CREATED: 'Conta Paper criada', PAPER_RISK_CHECK_APPROVED: 'Verificação de risco aprovada', PAPER_POSITION_OPENED: 'Posição simulada aberta', PAPER_ORDER_CANCELLED: 'Ordem simulada cancelada', PAPER_POSITION_CLOSED: 'Posição simulada fechada' };
  return <QueryState query={query}>{query.data?.items.length ? <ol className="vn-trading-timeline">{query.data.items.map((item) => <li key={item.id}><span><Clock3 size={16} /></span><div><strong>{eventLabels[item.event_type] ?? 'Evento Paper'}</strong><p>{item.symbol ? `${item.symbol} · ` : ''}{formatDateTime(item.created_at)}</p></div></li>)}</ol> : <Card><EmptyState title="Histórico ainda vazio" description="Sinais, verificações de risco e operações simuladas formarão uma trilha explicável aqui." /></Card>}</QueryState>;
}

export function TradingPage() {
  const households = useHouseholdList();
  const defaultHousehold = useHouseholdDefault();
  const [householdId, setHouseholdId] = useState<number | null>(null);
  const [active, setActive] = useState<TabId>('overview');
  useEffect(() => { if (householdId === null && defaultHousehold.data?.id) setHouseholdId(defaultHousehold.data.id); }, [defaultHousehold.data?.id, householdId]);
  const options = useMemo(() => households.data ?? [], [households.data]);

  return <div className="vn-page vn-trading-page">
    <SectionHeader eyebrow="Trading assistido" title="Trading" description="Simulação pessoal baseada no Trading V2. Nenhuma ordem real é executada." headingLevel={1} action={<Badge tone="warning">PAPER ONLY</Badge>} />
    <div className="vn-trading-banner"><FlaskConical size={20} /><div><strong>Ambiente de simulação</strong><p>Saldo, ordens, posições e resultados desta área são virtuais e não alteram seu patrimônio.</p></div></div>
    {options.length > 0 && <label className="vn-trading-household"><span>Contexto financeiro usado somente para leitura de risco</span><select value={householdId ?? ''} onChange={(event) => setHouseholdId(Number(event.target.value))}>{options.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>}
    <Tabs active={active} onChange={(id) => setActive(id as TabId)} tabs={[
      { id: 'overview', label: 'Resumo', content: <TradingSummary householdId={householdId} /> },
      { id: 'opportunities', label: 'Oportunidades', content: <Opportunities householdId={householdId} /> },
      { id: 'paper', label: 'Simulação', content: <PaperPortfolio /> },
      { id: 'backtests', label: 'Backtests', content: <Backtests /> },
      { id: 'models', label: 'Modelos', content: <Models /> },
      { id: 'history', label: 'Histórico', content: <Events /> },
    ]} />
    <footer className="vn-trading-footer"><Activity size={17} /><span>Trading real, corretoras e movimentação de capital permanecem desabilitados.</span></footer>
  </div>;
}
