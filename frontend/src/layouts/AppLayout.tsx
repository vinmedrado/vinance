import { NavLink, Outlet, useNavigate } from 'react-router-dom';
import { Brain, BriefcaseBusiness, ChartNoAxesCombined, CreditCard, Gauge, Goal, LayoutDashboard, LogOut, ReceiptText, Settings, ShieldCheck, Sparkles, WalletCards, FlaskConical, Search, Bell, UserRound, ChevronDown, Landmark, PiggyBank } from 'lucide-react';
import { logout } from '../services/api';
import vinanceLogo from '../assets/brand/vinance-logo-dark.png';

const groups = [
  { title: 'Financeiro', items: [['Dashboard','/',LayoutDashboard],['Receitas','/receitas',WalletCards],['Despesas','/despesas',ReceiptText],['Contas','/contas',BriefcaseBusiness],['Cartões','/cartoes',CreditCard],['Orçamento','/orcamento',Gauge],['Meu Plano','/plano-financeiro',Sparkles],['Advisor','/advisor',Brain],['Metas','/metas',Goal],['Diagnóstico','/diagnostico',Brain]] },
  { title: 'Investimentos', items: [['Investimentos','/investimentos',ChartNoAxesCombined],['Quant Lab','/quant-lab',FlaskConical],['Carteira','/carteira',WalletCards],['Alertas','/alertas',ShieldCheck]] },
  { title: 'Conta', items: [['Planos','/planos',Sparkles],['Configurações','/configuracoes',Settings]] },
];

const railItems = [
  { path: '/', icon: LayoutDashboard, label: 'Dashboard' },
  { path: '/receitas', icon: WalletCards, label: 'Receitas' },
  { path: '/despesas', icon: ReceiptText, label: 'Despesas' },
  { path: '/orcamento', icon: Gauge, label: 'Orçamento' },
  { path: '/quant-lab', icon: FlaskConical, label: 'Quant Lab' },
  { path: '/advisor', icon: Brain, label: 'Advisor' },
  { path: '/configuracoes', icon: Settings, label: 'Configurações' },
];

export default function AppLayout() {
  const navigate = useNavigate();
  return (
    <div className="fintech-shell">
      <aside className="icon-rail" aria-label="Navegação rápida">
        <div className="rail-logo"><img src={vinanceLogo} alt="Vinance" /></div>
        <div className="rail-nav">
          {railItems.map(({ path, icon: Icon, label }) => (
            <NavLink key={path} to={path} end={path === '/'} title={label} className={({ isActive }) => isActive ? 'active' : ''}>
              <Icon size={19} />
            </NavLink>
          ))}
        </div>
        <button className="rail-action" title="Sair" onClick={() => { logout(); navigate('/login'); }}><LogOut size={18} /></button>
      </aside>

      <aside className="sidebar app-panel-sidebar">
        <div className="brand compact-brand">
          <img className="brand-logo" src={vinanceLogo} alt="Vinance" />
          <div>
            <strong>Vinance</strong>
            <span>Capital Intelligence</span>
          </div>
        </div>

        <div className="finance-score-card">
          <span>Centro financeiro</span>
          <strong>Operação ativa</strong>
          <small>Caixa, despesas, orçamento e alocação conectados.</small>
        </div>

        {groups.map((g) => (
          <div className="nav-group" key={g.title}>
            <p>{g.title}</p>
            {g.items.map(([label, path, Icon]: any) => (
              <NavLink key={path} to={path} end={path === '/'} className={({ isActive }) => isActive ? 'active' : ''}>
                <Icon size={18} />
                <span>{label}</span>
              </NavLink>
            ))}
          </div>
        ))}
      </aside>

      <section className="workspace">
        <header className="topbar">
          <div className="topbar-search"><Search size={17} /><span>Buscar receita, despesa, ativo ou decisão...</span></div>
          <div className="topbar-actions">
            <button
              className="topbar-icon magic-hover"
              title="Notificações"
              onClick={() => {
                if (import.meta.env.VITE_DEMO_MODE === 'true') {
                  alert('Central de notificações premium em desenvolvimento.');
                  return;
                }

                navigate('/alertas');
              }}
            >
              <Bell size={17} />
            </button>

            <button
              className="topbar-icon magic-hover"
              title="Instituições financeiras"
              onClick={() => {
                if (import.meta.env.VITE_DEMO_MODE === 'true') {
                  alert('Integrações bancárias premium em desenvolvimento.');
                  return;
                }

                navigate('/contas');
              }}
            >
              <Landmark size={17} />
            </button>
            <button
              type="button"
              className="profile-chip magic-hover"
              title="Sair"
              onClick={() => {
                logout();
                navigate('/login');
              }}
            >
  <UserRound size={17} />
  <span>Sair</span>
  <LogOut size={15} />
</button>
          </div>
        </header>
        <main className="content">
          <div className="workspace-ribbon">
            <span><PiggyBank size={16}/> Sistema Financeiro Inteligente</span>
            <small>Receita → Despesa → Capital investível → Alocação recomendada</small>
          </div>
          <Outlet />
        </main>
      </section>
    </div>
  );
}
