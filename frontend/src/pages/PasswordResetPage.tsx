import { FormEvent, useState } from 'react';
import { Link } from 'react-router-dom';
import { Button, Card, Input } from '../components';
import { completePasswordRecovery, takeTokenFromFragment } from '../features/platform-access/services/access.service';
import { normalizeApiError } from '../services/api';

export function PasswordResetPage() {
  const [token, setToken] = useState(() => takeTokenFromFragment() ?? ''); const [password, setPassword] = useState(''); const [confirmation, setConfirmation] = useState(''); const [message, setMessage] = useState(''); const [error, setError] = useState(''); const [pending, setPending] = useState(false);
  async function submit(event: FormEvent) { event.preventDefault(); setPending(true); setError(''); try { const result = await completePasswordRecovery({ token, new_password: password, password_confirmation: confirmation }); setMessage(result.message); } catch (cause) { setError(normalizeApiError(cause).message); } finally { setPending(false); } }
  return <main className="vn-auth vn-auth--single"><Card className="vn-auth__card" title="Definir nova senha" description="O link é temporário e funciona uma única vez."><form className="vn-form" onSubmit={submit}><Input label="Código de recuperação" type="password" autoComplete="off" value={token} onChange={(event) => setToken(event.target.value)} required /><Input label="Nova senha" type="password" autoComplete="new-password" minLength={12} value={password} onChange={(event) => setPassword(event.target.value)} required /><Input label="Confirmar nova senha" type="password" autoComplete="new-password" minLength={12} value={confirmation} onChange={(event) => setConfirmation(event.target.value)} required />{message && <p className="vn-session-notice" role="status">{message}</p>}{error && <p className="vn-error" role="alert">{error}</p>}<Button type="submit" disabled={pending}>{pending ? 'Atualizando…' : 'Redefinir senha'}</Button><Link to="/login">Voltar para entrar</Link></form></Card></main>;
}
