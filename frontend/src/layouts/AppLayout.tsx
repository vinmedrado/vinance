import { NavLink, Outlet, useNavigate } from 'react-router-dom';
import { BarChart3, Brain, Landmark, LayoutDashboard, LogOut, MessageCircle, ShieldCheck, WalletCards, TrendingUp } from 'lucide-react';
import { Button } from '../components';
import { useLogout, useCurrentUser } from '../features/auth/hooks/useAuth';
import { useThemeMode } from '../hooks/useThemeMode';

const navItems = [
  { label: 'Dashboard', path: '/dashboard', icon: LayoutDashboard },
  { label: 'Financeiro', path: '/financial', icon: WalletCards },
  { label: 'Mercado', path: '/market', icon: BarChart3 },
  { label: 'Inteligência', path: '/intelligence', icon: Brain },
  { label: 'Investir', path: '/investir', icon: TrendingUp },
  { label: 'Advisor IA', path: '/advisor', icon: MessageCircle },
];

export function AppLayout() {
  const navigate = useNavigate();
  const signOut = useLogout();
  const { data: user } = useCurrentUser();
  const { mode, setMode } = useThemeMode();

  async function handleLogout() {
    await signOut();
    navigate('/login', { replace: true });
  }

  return (
    <div className="vn-shell">
      <aside className="vn-sidebar">
        <div className="vn-brand" aria-label="Vinance">
          <div className="vn-brand__mark"><Landmark size={22} /></div>
          <div><strong>Vinance</strong><span>Inteligência financeira brasileira</span></div>
        </div>
        <nav className="vn-nav" aria-label="Navegação principal">
          {navItems.map((item) => {
            const Icon = item.icon;
            return <NavLink key={item.path} to={item.path} className={({ isActive }) => isActive ? 'active' : ''}><Icon size={18} /><span>{item.label}</span></NavLink>;
          })}
        </nav>
        <div className="vn-sidebar__note">
          <ShieldCheck size={18} />
          <p>Base educacional. Sem promessa de retorno e sem recomendação definitiva de compra.</p>
        </div>
      </aside>
      <main className="vn-main">
        <header className="vn-topbar">
          <div><span className="vn-kicker">Vinance v2</span><strong>{user?.full_name || user?.email || 'Sessão autenticada'}</strong></div>
          <div className="vn-topbar__actions">
            <Button variant="ghost" onClick={() => setMode(mode === 'dark' ? 'light' : 'dark')}>{mode === 'dark' ? 'Tema claro' : 'Tema escuro'}</Button>
            <Button variant="secondary" onClick={handleLogout}><LogOut size={16} /> Sair</Button>
          </div>
        </header>
        <div className="vn-content"><Outlet /></div>
      </main>
    </div>
  );
}
