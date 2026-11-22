import { FormEvent, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Button, Card, Input, SectionHeader } from '../components';
import {
  cancelPlatformInvitation,
  createPlatformInvitation,
  issuePasswordResetLink,
  listPlatformInvitations,
  listPlatformUsers,
  resendPlatformInvitation,
  setPlatformUserActive,
} from '../features/platform-access/services/access.service';
import type { InvitationIssued } from '../features/platform-access/types/access.types';
import { normalizeApiError } from '../services/api';

export function AccessAdministrationPage() {
  const client = useQueryClient(); const [email, setEmail] = useState(''); const [issued, setIssued] = useState<InvitationIssued | null>(null); const [resetLink, setResetLink] = useState(''); const [error, setError] = useState('');
  const users = useQuery({ queryKey: ['platform-access', 'users'], queryFn: listPlatformUsers });
  const invitations = useQuery({ queryKey: ['platform-access', 'invitations'], queryFn: listPlatformInvitations });
  const refresh = () => client.invalidateQueries({ queryKey: ['platform-access'] });
  const invite = useMutation({ mutationFn: createPlatformInvitation, onSuccess: (result) => { setIssued(result); setEmail(''); refresh(); } });
  async function submit(event: FormEvent) { event.preventDefault(); setError(''); try { await invite.mutateAsync(email); } catch (cause) { setError(normalizeApiError(cause).message); } }
  async function act(action: () => Promise<unknown>) { setError(''); try { await action(); refresh(); } catch (cause) { setError(normalizeApiError(cause).message); } }
  function absolute(path: string) { return `${window.location.origin}${path}`; }
  return <div className="vn-page"><SectionHeader eyebrow="Administração" title="Pessoas e acesso" description="Convites para usar o Vinance são separados dos convites para Finanças do casal." />{error && <p className="vn-error" role="alert">{error}</p>}<Card title="Convidar pessoa" description="Cada pessoa começa com finanças pessoais privadas."><form className="vn-inline-form" onSubmit={submit}><Input label="E-mail" type="email" value={email} onChange={(event) => setEmail(event.target.value)} required /><Button type="submit" disabled={invite.isPending}>Criar convite</Button></form>{issued && <div className="vn-manual-link" role="status"><strong>{issued.message}</strong><p>Este link aparece somente nesta operação:</p><code>{absolute(issued.registration_path)}</code><Button type="button" variant="secondary" onClick={() => navigator.clipboard.writeText(absolute(issued.registration_path))}>Copiar link</Button></div>}</Card><Card title="Convites pendentes"><div className="vn-data-list">{(invitations.data ?? []).map((item) => <article key={item.id}><div><strong>{item.email_normalized}</strong><span>{item.status} · Cloudflare: {item.cloudflare_access_status}</span></div>{item.status === 'PENDING' && <div className="vn-inline-actions"><Button variant="ghost" onClick={() => act(async () => setIssued(await resendPlatformInvitation(item.id)))}>Gerar novo link</Button><Button variant="secondary" onClick={() => act(() => cancelPlatformInvitation(item.id))}>Cancelar</Button></div>}</article>)}{invitations.data?.length === 0 && <p>Nenhum convite criado.</p>}</div></Card><Card title="Contas"><div className="vn-data-list">{(users.data ?? []).map((user) => <article key={user.id}><div><strong>{user.full_name || user.email}</strong><span>{user.email} · {user.is_platform_admin ? 'Administrador da plataforma' : 'Usuário'} · {user.is_active ? 'Ativo' : 'Inativo'}</span></div><div className="vn-inline-actions"><Button variant="ghost" onClick={() => act(async () => { const result = await issuePasswordResetLink(user.id); setResetLink(absolute(result.reset_path)); })}>Gerar recuperação</Button><Button variant="secondary" onClick={() => act(() => setPlatformUserActive(user.id, !user.is_active))}>{user.is_active ? 'Desativar' : 'Reativar'}</Button></div></article>)}</div>{resetLink && <div className="vn-manual-link" role="status"><p>Link de recuperação de uso único:</p><code>{resetLink}</code><Button type="button" variant="secondary" onClick={() => navigator.clipboard.writeText(resetLink)}>Copiar link</Button></div>}</Card></div>;
}
