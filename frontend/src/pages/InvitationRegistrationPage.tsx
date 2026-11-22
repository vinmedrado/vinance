import { FormEvent, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Button, Card, Input } from '../components';
import { acceptPlatformInvitation, takeTokenFromFragment } from '../features/platform-access/services/access.service';
import { normalizeApiError } from '../services/api';

export function InvitationRegistrationPage() {
  const navigate = useNavigate();
  const [token, setToken] = useState(() => takeTokenFromFragment() ?? '');
  const [form, setForm] = useState({ full_name: '', email: '', password: '', password_confirmation: '' });
  const [privacy, setPrivacy] = useState(false); const [error, setError] = useState(''); const [pending, setPending] = useState(false);
  async function submit(event: FormEvent) { event.preventDefault(); setPending(true); setError(''); try { await acceptPlatformInvitation({ ...form, token, privacy_acknowledged: privacy }); navigate('/dashboard', { replace: true }); } catch (cause) { setError(normalizeApiError(cause).message); } finally { setPending(false); } }
  return <main className="vn-auth vn-auth--single"><Card className="vn-auth__card" title="Criar conta por convite" description="Sua nova conta começa com finanças pessoais privadas. Convites para Finanças do casal são separados."><form className="vn-form" onSubmit={submit}><Input label="Código do convite" type="password" autoComplete="off" value={token} onChange={(event) => setToken(event.target.value)} required /><Input label="Nome completo" autoComplete="name" value={form.full_name} onChange={(event) => setForm({ ...form, full_name: event.target.value })} required /><Input label="E-mail convidado" type="email" autoComplete="email" value={form.email} onChange={(event) => setForm({ ...form, email: event.target.value })} required /><Input label="Senha" type="password" autoComplete="new-password" minLength={12} value={form.password} onChange={(event) => setForm({ ...form, password: event.target.value })} required /><Input label="Confirmar senha" type="password" autoComplete="new-password" minLength={12} value={form.password_confirmation} onChange={(event) => setForm({ ...form, password_confirmation: event.target.value })} required /><label className="vn-check"><input type="checkbox" checked={privacy} onChange={(event) => setPrivacy(event.target.checked)} required /><span>Compreendo como meus dados privados serão tratados.</span></label>{error && <p className="vn-error" role="alert">{error}</p>}<Button type="submit" disabled={pending}>{pending ? 'Criando conta…' : 'Criar minha conta'}</Button><Link to="/login">Voltar para entrar</Link></form></Card></main>;
}
