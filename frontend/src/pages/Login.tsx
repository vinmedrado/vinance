import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { LockKeyhole, LineChart, WalletCards, UserPlus, ArrowRight, ShieldCheck } from 'lucide-react';
import { login, register } from '../services/api';
import { Button, Callout, MetricCard } from '../components/ui';
import vinanceLogo from '../assets/brand/vinance-logo-dark.png';

export default function Login() {
  const navigate = useNavigate();
  const [mode, setMode] = useState<'login' | 'register'>('login');
  const [name, setName] = useState('');
  const [organization, setOrganization] = useState('');
  const [email, setEmail] = useState('demo@financeos.local');
  const [password, setPassword] = useState('financeos123');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      if (mode === 'register') {
        await register({
          email,
          password,
          full_name: name || undefined,
          organization_name: organization || name || undefined,
        });
      } else {
        await login(email, password);
      }

      navigate('/');
    } catch (err: any) {
      const detail = err?.response?.data?.detail;
      setError(
        detail ||
          (mode === 'register'
            ? 'Não foi possível criar sua conta.'
            : 'Não foi possível entrar. Confira seus dados ou use o modo demo local.'),
      );
    } finally {
      setLoading(false);
    }
  }

  function useDemo() {
    setMode('login');
    setEmail('demo@financeos.local');
    setPassword('financeos123');
    setError('');
  }

  return (
    <div className={`auth-page auth-motion-page ${mode === 'register' ? 'is-register' : 'is-login'}`}>
      <div className="auth-showcase">
        <div className="auth-logo-line">
          <img src={vinanceLogo} alt="Vinance" />
          <span>Vinance</span>
        </div>

        <span className="eyebrow">Capital Intelligence OS</span>

        <h1>Controle financeiro com método, clareza e decisão de investimento.</h1>

        <p>
          Cadastre receitas e despesas. O Vinance calcula o capital investível,
          recomenda o método financeiro e orienta a alocação por perfil de risco.
        </p>

        <div className="grid two auth-proof-grid">
          <MetricCard
            icon={<WalletCards size={18} />}
            label="Fluxo"
            value="Caixa"
            hint="Receita, despesa e saldo livre"
          />

          <MetricCard
            icon={<LineChart size={18} />}
            label="Decisão"
            value="Alocação"
            hint="Quanto investir e onde posicionar"
          />
        </div>
      </div>

      <section className="auth-switch-card">
        <div className="auth-orb" />

        <div className="auth-tabs" role="tablist">
          <button
            className={mode === 'login' ? 'active' : ''}
            onClick={() => {
              setMode('login');
              setError('');
            }}
            type="button"
          >
            Entrar
          </button>

          <button
            className={mode === 'register' ? 'active' : ''}
            onClick={() => {
              setMode('register');
              setError('');
            }}
            type="button"
          >
            Criar conta
          </button>

          <span className="auth-tab-indicator" />
        </div>

        <div className="auth-slider">
          {mode === 'login' ? (
            <form onSubmit={submit} className="auth-pane login-pane form">
              <div className="auth-title-row">
                <LockKeyhole size={20} />
                <div>
                  <h2>Entrar no Vinance</h2>
                  <p>Acesse sua mesa financeira.</p>
                </div>
              </div>

              {error && <Callout title="Acesso não concluído" message={error} tone="danger" />}

              <label>
                E-mail
                <input value={email} onChange={(e) => setEmail(e.target.value)} placeholder="voce@email.com" />
              </label>

              <label>
                Senha
                <input
                  value={password}
                  type="password"
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="sua senha"
                />
              </label>

              <Button disabled={loading} className="magic-button">
                {loading ? (
                  'Processando...'
                ) : (
                  <>
                    Entrar <ArrowRight size={17} />
                  </>
                )}
              </Button>

              <button className="link-button" type="button" onClick={useDemo}>
                Usar demo local
              </button>
            </form>
          ) : (
            <form onSubmit={submit} className="auth-pane register-pane form">
              <div className="auth-title-row">
                <UserPlus size={20} />
                <div>
                  <h2>Criar conta</h2>
                  <p>Abra seu ambiente real.</p>
                </div>
              </div>

              {error && <Callout title="Cadastro não concluído" message={error} tone="danger" />}

              <label>
                Nome
                <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Seu nome" />
              </label>

              <label>
                Organização
                <input
                  value={organization}
                  onChange={(e) => setOrganization(e.target.value)}
                  placeholder="Ex.: Vinance pessoal"
                />
              </label>

              <label>
                E-mail
                <input value={email} onChange={(e) => setEmail(e.target.value)} placeholder="voce@email.com" />
              </label>

              <label>
                Senha
                <input
                  value={password}
                  type="password"
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="use letras, números e símbolos"
                />
              </label>

              <Button disabled={loading} className="magic-button">
                {loading ? (
                  'Criando...'
                ) : (
                  <>
                    Criar conta <ShieldCheck size={17} />
                  </>
                )}
              </Button>
            </form>
          )}
        </div>
      </section>
    </div>
  );
}