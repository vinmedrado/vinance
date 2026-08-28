import { FormEvent, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { Landmark } from 'lucide-react';
import { Button, Card, Input } from '../components';
import { useLogin, useRegister } from '../features/auth/hooks/useAuth';
import type { ApiErrorShape } from '../services/api';

export function LoginPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const login = useLogin();
  const register = useRegister();
  const [mode, setMode] = useState<'login' | 'register'>('login');
  const [fullName, setFullName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const routeState = location.state as { from?: string; reason?: 'required' | 'expired' | 'invalid' } | null;
  const requestedPath = routeState?.from;
  const redirectTo = requestedPath?.startsWith('/') && !requestedPath.startsWith('//') ? requestedPath : '/dashboard';
  const error = (login.error || register.error) as ApiErrorShape | null;
  const isPending = login.isPending || register.isPending;
  const sessionNotice = routeState?.reason === 'expired'
    ? 'Sua sessão expirou. Entre novamente para continuar.'
    : routeState?.reason === 'invalid'
      ? 'Sua sessão não é mais válida. Entre novamente para continuar.'
      : routeState?.reason === 'required'
        ? 'Entre para acessar a central de decisão.'
        : null;

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    try {
      if (mode === 'login') await login.mutateAsync({ email, password });
      else await register.mutateAsync({ email, password, full_name: fullName || undefined });
      navigate(redirectTo, { replace: true });
    } catch {
      // O estado da mutation apresenta o erro normalizado no próprio formulário.
    }
  }

  return (
    <main className="vn-auth">
      <section className="vn-auth__hero">
        <div className="vn-brand vn-brand--large"><div className="vn-brand__mark"><Landmark size={24} /></div><div><strong>Vinance</strong><span>Seu centro de inteligência financeira</span></div></div>
        <h1>Finanças pessoais com leitura de risco, mercado e contexto.</h1>
        <p>Entre com uma conta real do backend FastAPI para acessar diagnóstico, inteligência heurística e advisor conectado.</p>
      </section>
      <Card className="vn-auth__card" title={mode === 'login' ? 'Entrar' : 'Criar conta'} description="Autenticação real via backend aprovado. O token é salvo localmente e limpo no logout.">
        <form className="vn-form" onSubmit={handleSubmit}>
          {sessionNotice && <p className="vn-session-notice" role="status">{sessionNotice}</p>}
          {mode === 'register' && <Input label="Nome" placeholder="Nome completo" value={fullName} onChange={(event) => setFullName(event.target.value)} />}
          <Input label="E-mail" placeholder="voce@email.com" type="email" autoComplete="email" value={email} onChange={(event) => setEmail(event.target.value)} required />
          <Input label="Senha" placeholder="••••••••" type="password" autoComplete={mode === 'login' ? 'current-password' : 'new-password'} value={password} onChange={(event) => setPassword(event.target.value)} minLength={8} required />
          {error && <p className="vn-error" role="alert">{error.message}</p>}
          <Button type="submit" disabled={isPending}>{isPending ? 'Conectando...' : mode === 'login' ? 'Entrar' : 'Registrar e entrar'}</Button>
          <Button type="button" variant="ghost" onClick={() => { login.reset(); register.reset(); setMode(mode === 'login' ? 'register' : 'login'); }}>
            {mode === 'login' ? 'Criar nova conta' : 'Já tenho conta'}
          </Button>
          <p className="vn-disclaimer">Sem token demo e sem mock paralelo de autenticação.</p>
        </form>
      </Card>
    </main>
  );
}
