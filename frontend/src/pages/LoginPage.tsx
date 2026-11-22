import { FormEvent, useEffect, useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { Landmark } from 'lucide-react';
import { Button, Card, Input } from '../components';
import { useLogin } from '../features/auth/hooks/useAuth';
import { getAccessCapabilities } from '../features/platform-access/services/access.service';
import type { AccessCapabilities } from '../features/platform-access/types/access.types';
import type { ApiErrorShape } from '../services/api';

export function LoginPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const login = useLogin();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [capabilities, setCapabilities] = useState<AccessCapabilities | null>(null);
  const routeState = location.state as { from?: string; reason?: 'required' | 'expired' | 'invalid' | 'password-changed' } | null;
  const requestedPath = routeState?.from;
  const redirectTo = requestedPath?.startsWith('/') && !requestedPath.startsWith('//') ? requestedPath : '/dashboard';
  const error = login.error as ApiErrorShape | null;

  useEffect(() => {
    let active = true;
    getAccessCapabilities().then((value) => { if (active) setCapabilities(value); }).catch(() => undefined);
    return () => { active = false; };
  }, []);

  const sessionNotice = routeState?.reason === 'password-changed'
    ? 'Senha alterada. Entre novamente com sua nova senha.'
    : routeState?.reason === 'expired'
      ? 'Sua sessão expirou. Entre novamente para continuar.'
      : routeState?.reason === 'invalid'
        ? 'Sua sessão não é mais válida. Entre novamente para continuar.'
        : routeState?.reason === 'required'
          ? 'Entre para acessar a central de decisão.'
          : null;

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    try {
      await login.mutateAsync({ email, password });
      navigate(redirectTo, { replace: true });
    } catch {
      // A mutation apresenta o erro normalizado no próprio formulário.
    }
  }

  return (
    <main className="vn-auth">
      <section className="vn-auth__hero">
        <div className="vn-brand vn-brand--large"><div className="vn-brand__mark"><Landmark size={24} /></div><div><strong>Vinance</strong><span>Seu centro de inteligência financeira</span></div></div>
        <h1>Suas finanças, prioridades e próximos passos em um só lugar.</h1>
        <p>Entre para acompanhar sua situação financeira, seus investimentos e as decisões preparadas pelo Vinance.</p>
      </section>
      <Card className="vn-auth__card" title="Entrar" description="Acesso privado com sessão protegida e renovável.">
        <form className="vn-form" onSubmit={handleSubmit}>
          {sessionNotice && <p className="vn-session-notice" role="status">{sessionNotice}</p>}
          <Input label="E-mail" placeholder="voce@email.com" type="email" autoComplete="email" value={email} onChange={(event) => setEmail(event.target.value)} required />
          <Input label="Senha" placeholder="••••••••" type="password" autoComplete="current-password" value={password} onChange={(event) => setPassword(event.target.value)} required />
          {error && <p className="vn-error" role="alert">{error.message}</p>}
          <Button type="submit" disabled={login.isPending}>{login.isPending ? 'Entrando…' : 'Entrar'}</Button>
          <nav className="vn-auth-links" aria-label="Acesso à conta">
            <Link to="/access/invitation">Tenho um convite</Link>
            <Link to="/access/recover">Recuperar acesso</Link>
            {capabilities?.bootstrap_available && <Link to="/access/bootstrap">Configurar primeira conta</Link>}
          </nav>
          <p className="vn-disclaimer">Novas contas são criadas somente por convite autorizado.</p>
        </form>
      </Card>
    </main>
  );
}
