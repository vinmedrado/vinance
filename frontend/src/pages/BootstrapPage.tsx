import { FormEvent, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Button, Card, Input } from '../components';
import { bootstrapAccount } from '../features/platform-access/services/access.service';
import { normalizeApiError } from '../services/api';

export function BootstrapPage() {
  const navigate = useNavigate();
  const [form, setForm] = useState({ full_name: '', email: '', password: '', password_confirmation: '', bootstrap_credential: '' });
  const [privacy, setPrivacy] = useState(false);
  const [error, setError] = useState('');
  const [pending, setPending] = useState(false);
  async function submit(event: FormEvent) { event.preventDefault(); setPending(true); setError(''); try { await bootstrapAccount({ ...form, privacy_acknowledged: privacy }); navigate('/dashboard', { replace: true }); } catch (cause) { setError(normalizeApiError(cause).message); } finally { setPending(false); } }
  return <main className="vn-auth vn-auth--single"><Card className="vn-auth__card" title="Configurar primeira conta" description="Use a credencial inicial de uso único fornecida pelo administrador do ambiente."><form className="vn-form" onSubmit={submit}><Input label="Nome completo" autoComplete="name" value={form.full_name} onChange={(event) => setForm({ ...form, full_name: event.target.value })} required /><Input label="E-mail" type="email" autoComplete="email" value={form.email} onChange={(event) => setForm({ ...form, email: event.target.value })} required /><Input label="Senha" type="password" autoComplete="new-password" minLength={12} value={form.password} onChange={(event) => setForm({ ...form, password: event.target.value })} required /><Input label="Confirmar senha" type="password" autoComplete="new-password" minLength={12} value={form.password_confirmation} onChange={(event) => setForm({ ...form, password_confirmation: event.target.value })} required /><Input label="Credencial inicial" type="password" autoComplete="off" value={form.bootstrap_credential} onChange={(event) => setForm({ ...form, bootstrap_credential: event.target.value })} required /><label className="vn-check"><input type="checkbox" checked={privacy} onChange={(event) => setPrivacy(event.target.checked)} required /><span>Li e compreendo que minha conta armazenará dados financeiros privados.</span></label>{error && <p className="vn-error" role="alert">{error}</p>}<Button type="submit" disabled={pending}>{pending ? 'Configurando…' : 'Criar conta administrativa'}</Button><Link to="/login">Voltar para entrar</Link></form></Card></main>;
}
