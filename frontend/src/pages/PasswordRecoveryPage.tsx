import { FormEvent, useState } from 'react';
import { Link } from 'react-router-dom';
import { Button, Card, Input } from '../components';
import { requestPasswordRecovery } from '../features/platform-access/services/access.service';
import { normalizeApiError } from '../services/api';

export function PasswordRecoveryPage() {
  const [email, setEmail] = useState(''); const [message, setMessage] = useState(''); const [error, setError] = useState(''); const [pending, setPending] = useState(false);
  async function submit(event: FormEvent) { event.preventDefault(); setPending(true); setError(''); try { const result = await requestPasswordRecovery(email); setMessage(result.message); } catch (cause) { setError(normalizeApiError(cause).message); } finally { setPending(false); } }
  return <main className="vn-auth vn-auth--single"><Card className="vn-auth__card" title="Recuperar acesso" description="A resposta não confirma se o e-mail possui conta."><form className="vn-form" onSubmit={submit}><Input label="E-mail" type="email" autoComplete="email" value={email} onChange={(event) => setEmail(event.target.value)} required />{message && <p className="vn-session-notice" role="status">{message}</p>}{error && <p className="vn-error" role="alert">{error}</p>}<Button type="submit" disabled={pending}>{pending ? 'Verificando…' : 'Solicitar recuperação'}</Button><Link to="/login">Voltar para entrar</Link></form></Card></main>;
}
