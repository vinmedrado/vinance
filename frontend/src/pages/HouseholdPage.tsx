import { FormEvent, useEffect, useMemo, useRef, useState } from 'react';
import { Badge, Button, Card, EmptyState, ErrorState, Input, LoadingState, Modal, SectionHeader, SelectField, Toast } from '../components';
import { useCurrentUser, useSessionToken } from '../features/auth/hooks/useAuth';
import {
  useCancelInvitation,
  useCreateHousehold,
  useCreateInvitation,
  useHouseholdDefault,
  useHouseholdList,
  useHouseholdMembers,
  useIncomingInvitations,
  useInvitationDecision,
  useLeaveHousehold,
  useOutgoingInvitations,
  useRemoveMember,
  useSetDefaultHousehold,
  useUpdateMemberRole,
} from '../features/household/hooks/useHousehold';
import type { HouseholdRole } from '../features/household/types/household.types';

function message(error: unknown) {
  return error instanceof Error ? error.message : 'Não foi possível concluir esta ação.';
}

export function HouseholdPage() {
  const sessionToken = useSessionToken();
  const currentUser = useCurrentUser();
  const households = useHouseholdList();
  const defaultHousehold = useHouseholdDefault();
  const incoming = useIncomingInvitations();
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [pendingSwitchId, setPendingSwitchId] = useState<number | null>(null);
  const [newHouseholdName, setNewHouseholdName] = useState('');
  const [inviteEmail, setInviteEmail] = useState('');
  const [inviteRole, setInviteRole] = useState<HouseholdRole>('MEMBER');
  const [notice, setNotice] = useState<string | null>(null);
  const previousSession = useRef(sessionToken);

  const members = useHouseholdMembers(selectedId);
  const currentMembership = members.data?.find((member) => member.user_id === currentUser.data?.id);
  const isOwner = currentMembership?.role === 'OWNER';
  const isSoleOwner = isOwner && (members.data ?? []).filter((member) => member.role === 'OWNER').length === 1;
  const outgoing = useOutgoingInvitations(selectedId, Boolean(isOwner));
  const createHousehold = useCreateHousehold();
  const createInvitation = useCreateInvitation();
  const acceptInvitation = useInvitationDecision('accept');
  const declineInvitation = useInvitationDecision('decline');
  const cancelInvitation = useCancelInvitation();
  const updateRole = useUpdateMemberRole();
  const removeMember = useRemoveMember();
  const setDefault = useSetDefaultHousehold();
  const leave = useLeaveHousehold();

  const selected = households.data?.find((household) => household.id === selectedId) ?? null;
  const dirty = newHouseholdName.trim().length > 0 || inviteEmail.trim().length > 0;
  const pending = [
    createHousehold,
    createInvitation,
    acceptInvitation,
    declineInvitation,
    cancelInvitation,
    updateRole,
    removeMember,
    setDefault,
    leave,
  ].some((mutation) => mutation.isPending);
  const actionError = [
    createHousehold.error,
    createInvitation.error,
    acceptInvitation.error,
    declineInvitation.error,
    cancelInvitation.error,
    updateRole.error,
    removeMember.error,
    setDefault.error,
    leave.error,
  ].find(Boolean);

  useEffect(() => {
    if (selectedId === null && defaultHousehold.data) setSelectedId(defaultHousehold.data.id);
  }, [defaultHousehold.data, selectedId]);

  useEffect(() => {
    if (!households.data?.length) return;
    if (selectedId !== null && households.data.some((item) => item.id === selectedId)) return;
    setSelectedId(defaultHousehold.data?.id ?? households.data[0].id);
  }, [defaultHousehold.data?.id, households.data, selectedId]);

  useEffect(() => {
    if (previousSession.current === sessionToken) return;
    previousSession.current = sessionToken;
    setSelectedId(null);
    setPendingSwitchId(null);
    setNewHouseholdName('');
    setInviteEmail('');
    setInviteRole('MEMBER');
    setNotice(null);
  }, [sessionToken]);

  useEffect(() => {
    if (!notice) return;
    const timeout = window.setTimeout(() => setNotice(null), 3500);
    return () => window.clearTimeout(timeout);
  }, [notice]);

  const pendingIncoming = useMemo(
    () => (incoming.data ?? []).filter((invitation) => invitation.status === 'PENDING'),
    [incoming.data],
  );

  function chooseHousehold(nextId: number) {
    if (pending || nextId === selectedId) return;
    if (dirty) {
      setPendingSwitchId(nextId);
      return;
    }
    setSelectedId(nextId);
  }

  function discardAndSwitch() {
    if (pendingSwitchId === null) return;
    setNewHouseholdName('');
    setInviteEmail('');
    setInviteRole('MEMBER');
    setSelectedId(pendingSwitchId);
    setPendingSwitchId(null);
  }

  async function submitHousehold(event: FormEvent) {
    event.preventDefault();
    const name = newHouseholdName.trim();
    if (!name) return;
    const created = await createHousehold.mutateAsync({
      householdId: 0,
      sessionToken,
      payload: { name },
    });
    setNewHouseholdName('');
    setSelectedId(created.id);
    setNotice('Household compartilhado criado.');
  }

  async function submitInvitation(event: FormEvent) {
    event.preventDefault();
    if (selectedId === null || selected?.household_type !== 'SHARED') return;
    await createInvitation.mutateAsync({
      householdId: selectedId,
      sessionToken,
      payload: { email: inviteEmail.trim(), role: inviteRole },
    });
    setInviteEmail('');
    setInviteRole('MEMBER');
    setNotice('Convite criado. A pessoa poderá aceitar ao entrar no Vinance.');
  }

  if (households.isLoading || defaultHousehold.isLoading || currentUser.isLoading) {
    return <LoadingState label="Carregando sua casa e família..." />;
  }

  return (
    <section className="vn-page">
      <SectionHeader
        eyebrow="Household"
        title="Casa e família"
        description="Cada pessoa mantém seus dados pessoais privados e compartilha somente o que escolher com a casa."
      />

      {(households.error || defaultHousehold.error || incoming.error) && (
        <Card><ErrorState title="Não foi possível carregar os households" description={message(households.error || defaultHousehold.error || incoming.error)} /></Card>
      )}
      {actionError && <Card><ErrorState title="A ação não foi concluída" description={message(actionError)} /></Card>}
      {notice && <Toast message={notice} />}

      <Card title="Convites para você" description="Entrar em uma casa compartilhada sempre exige seu aceite.">
        {pendingIncoming.length === 0 ? (
          <EmptyState title="Nenhum convite pendente" description="Quando alguém convidar seu e-mail, o convite aparecerá aqui." />
        ) : (
          <div className="vn-list">
            {pendingIncoming.map((invitation) => (
              <div key={invitation.id}>
                <div><strong>{invitation.household_name}</strong><p>Convite de {invitation.invited_by_name || 'um membro'} · papel {invitation.role === 'OWNER' ? 'proprietário' : 'membro'}</p></div>
                <div className="vn-inline-actions">
                  <Button disabled={pending} onClick={() => acceptInvitation.mutate({ invitationId: invitation.id, sessionToken })}>Aceitar</Button>
                  <Button variant="secondary" disabled={pending} onClick={() => declineInvitation.mutate({ invitationId: invitation.id, sessionToken })}>Recusar</Button>
                </div>
              </div>
            ))}
          </div>
        )}
      </Card>

      <div className="vn-grid vn-grid--two">
        <Card title="Seus households" description="Seu household pessoal continua privado. O compartilhado é separado.">
          <SelectField
            label="Household atual"
            value={selectedId ?? ''}
            disabled={pending}
            onChange={(event) => chooseHousehold(Number(event.target.value))}
            options={(households.data ?? []).map((item) => ({
              value: String(item.id),
              label: `${item.name} · ${item.household_type === 'PERSONAL' ? 'Pessoal' : 'Compartilhado'}${item.id === defaultHousehold.data?.id ? ' · Padrão' : ''}`,
            }))}
          />
          {selected && (
            <div className="vn-inline-actions">
              <Badge tone={selected.household_type === 'PERSONAL' ? 'warning' : 'success'}>{selected.household_type === 'PERSONAL' ? 'Privado' : 'Compartilhado'}</Badge>
              {selected.id === defaultHousehold.data?.id ? <Badge tone="success">Padrão</Badge> : (
                <Button variant="secondary" disabled={pending} onClick={() => setDefault.mutate({ householdId: selected.id, sessionToken, payload: undefined })}>Definir como padrão</Button>
              )}
            </div>
          )}
        </Card>

        <Card title="Criar household compartilhado" description="O novo espaço não substitui nem abre seu household pessoal.">
          <form className="vn-form" onSubmit={submitHousehold}>
            <Input label="Nome da casa" value={newHouseholdName} onChange={(event) => setNewHouseholdName(event.target.value)} placeholder="Casa Medrado" maxLength={255} required />
            <Button type="submit" disabled={pending || !newHouseholdName.trim()}>{createHousehold.isPending ? 'Criando...' : 'Criar compartilhado'}</Button>
          </form>
        </Card>
      </div>

      {selected && (
        <Card title={selected.name} description={selected.household_type === 'PERSONAL' ? 'Este espaço aceita somente você e não pode receber convites.' : 'Membros ativos veem apenas registros marcados como compartilhados.'}>
          {members.isLoading ? <LoadingState label="Carregando membros..." /> : (
            <div className="vn-list">
              {(members.data ?? []).map((member) => (
                <div key={member.id}>
                  <div>
                    <strong>{member.full_name || member.email || `Usuário ${member.user_id}`}</strong>
                    <p>{member.role === 'OWNER' ? 'Proprietário' : 'Membro'}{member.user_id === currentUser.data?.id ? ' · Você' : ''}</p>
                  </div>
                  {isOwner && selected.household_type === 'SHARED' && member.user_id !== currentUser.data?.id && (
                    <div className="vn-inline-actions">
                      <SelectField
                        label="Papel"
                        value={member.role}
                        disabled={pending}
                        onChange={(event) => updateRole.mutate({
                          householdId: selected.id,
                          sessionToken,
                          payload: { memberId: member.id, role: event.target.value as HouseholdRole },
                        })}
                        options={[{ value: 'MEMBER', label: 'Membro' }, { value: 'OWNER', label: 'Proprietário' }]}
                      />
                      <Button variant="ghost" disabled={pending} onClick={() => {
                        if (window.confirm(`Remover ${member.full_name || member.email || 'este membro'} do household?`)) {
                          removeMember.mutate({ householdId: selected.id, sessionToken, payload: { memberId: member.id } });
                        }
                      }}>Remover</Button>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}

          {selected.household_type === 'SHARED' && currentMembership && (
            <div className="vn-inline-actions">
              <Button variant="ghost" disabled={pending || Boolean(isSoleOwner)} onClick={() => {
                if (window.confirm('Sair deste household? Seus dados pessoais não serão transferidos nem apagados.')) {
                  leave.mutate({ householdId: selected.id, sessionToken, payload: undefined });
                }
              }}>Sair do household</Button>
              {isSoleOwner && <small>Transfira o papel de proprietário antes de sair.</small>}
            </div>
          )}
        </Card>
      )}

      {selected?.household_type === 'SHARED' && isOwner && (
        <div className="vn-grid vn-grid--two">
          <Card title="Convidar pessoa" description="O acesso só começa depois que a pessoa aceitar o convite com o mesmo e-mail.">
            <form className="vn-form" onSubmit={submitInvitation}>
              <Input label="E-mail" type="email" value={inviteEmail} onChange={(event) => setInviteEmail(event.target.value)} required />
              <SelectField label="Papel inicial" value={inviteRole} onChange={(event) => setInviteRole(event.target.value as HouseholdRole)} options={[{ value: 'MEMBER', label: 'Membro' }, { value: 'OWNER', label: 'Proprietário' }]} />
              <Button type="submit" disabled={pending || !inviteEmail.trim()}>{createInvitation.isPending ? 'Convidando...' : 'Criar convite'}</Button>
            </form>
          </Card>

          <Card title="Convites do household" description="Convites pendentes ainda não concedem acesso.">
            {(outgoing.data ?? []).filter((item) => item.status === 'PENDING').length === 0 ? (
              <EmptyState title="Nenhum convite pendente" description="Convites criados aparecerão aqui até a decisão da pessoa." />
            ) : (
              <div className="vn-list">
                {(outgoing.data ?? []).filter((item) => item.status === 'PENDING').map((invitation) => (
                  <div key={invitation.id}>
                    <div><strong>{invitation.invited_email_normalized}</strong><p>{invitation.role === 'OWNER' ? 'Proprietário' : 'Membro'} · Pendente</p></div>
                    <Button variant="ghost" disabled={pending} onClick={() => cancelInvitation.mutate({ householdId: selected.id, sessionToken, payload: { invitationId: invitation.id } })}>Cancelar convite</Button>
                  </div>
                ))}
              </div>
            )}
          </Card>
        </div>
      )}

      <Modal open={pendingSwitchId !== null} title="Alterações não salvas" onClose={() => setPendingSwitchId(null)}>
        <p>Trocar de household descartará os dados ainda não enviados deste formulário.</p>
        <div className="vn-inline-actions">
          <Button variant="secondary" onClick={() => setPendingSwitchId(null)}>Cancelar</Button>
          <Button onClick={discardAndSwitch}>Descartar e trocar</Button>
        </div>
      </Modal>
    </section>
  );
}
