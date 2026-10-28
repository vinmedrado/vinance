import { useCallback, useEffect, useRef, useState } from 'react';
import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom';
import { BarChart3, Brain, FlaskConical, House, KeyRound, Landmark, LayoutDashboard, ListChecks, LogOut, Menu, MessageCircle, ShieldCheck, SunMoon, WalletCards, TrendingUp, X } from 'lucide-react';
import { Button } from '../components';
import { useLogout, useCurrentUser } from '../features/auth/hooks/useAuth';
import { useThemeMode } from '../hooks/useThemeMode';

type NavigationItem = {
  label: string;
  desktopLabel?: string;
  path: string;
  icon: typeof LayoutDashboard;
};

const primaryNavItems: NavigationItem[] = [
  { label: 'Início', path: '/dashboard', icon: LayoutDashboard },
  { label: 'Situação', desktopLabel: 'Minha situação', path: '/financial', icon: WalletCards },
  { label: 'Mercado', path: '/market', icon: BarChart3 },
  { label: 'Investir', path: '/investir', icon: TrendingUp },
  { label: 'Assistente', desktopLabel: 'Assistente financeiro', path: '/advisor', icon: MessageCircle },
];

const secondaryNavItems: NavigationItem[] = [
  { label: 'Dados financeiros', path: '/financial/manage', icon: ListChecks },
  { label: 'Casa e família', path: '/household', icon: House },
  { label: 'Análises', path: '/intelligence', icon: Brain },
  { label: 'Trading', desktopLabel: 'Trading simulado', path: '/trading', icon: FlaskConical },
  { label: 'Segurança', path: '/account/security', icon: KeyRound },
];

function NavigationLinks({ items, compact = false }: { items: NavigationItem[]; compact?: boolean }) {
  return items.map((item) => {
    const Icon = item.icon;
    return (
      <NavLink key={item.path} to={item.path} className={({ isActive }) => isActive ? 'active' : ''}>
        <Icon size={compact ? 20 : 18} aria-hidden="true" />
        <span>{compact ? item.label : (item.desktopLabel ?? item.label)}</span>
      </NavLink>
    );
  });
}

export function AppLayout() {
  const navigate = useNavigate();
  const location = useLocation();
  const signOut = useLogout();
  const { data: user } = useCurrentUser();
  const { mode, setMode } = useThemeMode();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const mobileMenuButtonRef = useRef<HTMLButtonElement>(null);
  const mobileMenuPanelRef = useRef<HTMLElement>(null);
  const mobileMenuCloseButtonRef = useRef<HTMLButtonElement>(null);

  const closeMobileMenu = useCallback((restoreFocus = true) => {
    setMobileMenuOpen(false);
    if (restoreFocus) mobileMenuButtonRef.current?.focus();
  }, []);

  useEffect(() => {
    setMobileMenuOpen(false);
  }, [location.pathname]);

  useEffect(() => {
    if (!mobileMenuOpen) return;

    const previousBodyOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    mobileMenuCloseButtonRef.current?.focus();

    function keepFocusInsideMenu(event: KeyboardEvent) {
      if (event.key === 'Escape') {
        event.preventDefault();
        closeMobileMenu();
        return;
      }

      if (event.key !== 'Tab') return;
      const focusable = Array.from(
        mobileMenuPanelRef.current?.querySelectorAll<HTMLElement>(
          'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])',
        ) ?? [],
      ).filter((element) => !element.hasAttribute('hidden'));
      if (focusable.length === 0) {
        event.preventDefault();
        mobileMenuPanelRef.current?.focus();
        return;
      }

      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    }

    window.addEventListener('keydown', keepFocusInsideMenu);
    return () => {
      document.body.style.overflow = previousBodyOverflow;
      window.removeEventListener('keydown', keepFocusInsideMenu);
    };
  }, [closeMobileMenu, mobileMenuOpen]);

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
          <span className="vn-nav__label">Principal</span>
          <NavigationLinks items={primaryNavItems} />
          <span className="vn-nav__label">Gestão e conta</span>
          <NavigationLinks items={secondaryNavItems} />
        </nav>
        <div className="vn-sidebar__note">
          <ShieldCheck size={18} />
          <p>Base educacional. Sem promessa de retorno e sem recomendação definitiva de compra.</p>
        </div>
      </aside>
      <main className="vn-main">
        <header className="vn-topbar">
          <div className="vn-topbar__identity">
            <span className="vn-topbar__product">Vinance</span>
            <strong>{user?.full_name || user?.email || 'Sessão autenticada'}</strong>
          </div>
          <div className="vn-topbar__actions vn-desktop-actions">
            <Button variant="ghost" onClick={() => setMode(mode === 'dark' ? 'light' : 'dark')}>{mode === 'dark' ? 'Tema claro' : 'Tema escuro'}</Button>
            <Button variant="secondary" onClick={handleLogout}><LogOut size={16} /> Sair</Button>
          </div>
          <button ref={mobileMenuButtonRef} className="vn-mobile-menu-button" type="button" aria-expanded={mobileMenuOpen} aria-controls="vn-mobile-menu" onClick={() => setMobileMenuOpen(true)}>
            <Menu size={21} aria-hidden="true" />
            <span>Menu</span>
          </button>
        </header>
        <div className="vn-content"><Outlet /></div>
      </main>

      <nav className="vn-bottom-nav" aria-label="Navegação principal no celular">
        <NavigationLinks items={primaryNavItems} compact />
      </nav>

      {mobileMenuOpen && (
        <div className="vn-mobile-menu" id="vn-mobile-menu" role="dialog" aria-modal="true" aria-labelledby="vn-mobile-menu-title">
          <button className="vn-mobile-menu__backdrop" type="button" aria-label="Fechar menu ao tocar fora" onClick={() => closeMobileMenu()} />
          <aside ref={mobileMenuPanelRef} className="vn-mobile-menu__panel" tabIndex={-1}>
            <header>
              <div>
                <span id="vn-mobile-menu-title">Conta</span>
                <strong>{user?.full_name || user?.email || 'Sessão autenticada'}</strong>
              </div>
              <button ref={mobileMenuCloseButtonRef} type="button" aria-label="Fechar menu" onClick={() => closeMobileMenu()}><X size={21} /></button>
            </header>
            <nav className="vn-mobile-secondary-nav" aria-label="Gestão e configurações">
              <NavigationLinks items={secondaryNavItems} />
            </nav>
            <div className="vn-mobile-menu__actions">
              <Button variant="ghost" onClick={() => setMode(mode === 'dark' ? 'light' : 'dark')}><SunMoon size={17} /> {mode === 'dark' ? 'Usar tema claro' : 'Usar tema escuro'}</Button>
              <Button variant="secondary" onClick={handleLogout}><LogOut size={17} /> Sair da conta</Button>
            </div>
          </aside>
        </div>
      )}
    </div>
  );
}
