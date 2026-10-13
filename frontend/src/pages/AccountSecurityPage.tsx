import { FormEvent, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button, Card, Input, SectionHeader } from '../components';
import { useChangePassword } from '../features/auth/hooks/useAuth';
import type { ApiErrorShape } from '../services/api';

export function AccountSecurityPage() {
  const navigate = useNavigate();
  const change = useChangePassword();
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmation, setConfirmation] = useState('');
  const [validationError, setValidationError] = useState('');

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (newPassword !== confirmation) {
      setValidationError('A confirmação não corresponde à nova senha.');
      return;
    }
    setValidationError('');
    try {
      await change.mutateAsync({ current_password: currentPassword, new_password: newPassword });
      navigate('/login', { replace: true, state: { reason: 'password-changed' } });
    } catch {
      // A mutation expõe a mensagem normalizada abaixo.
    }
  }

  const apiError = change.error as ApiErrorShape | null;
  return (
    <section className="vn-page">
      <SectionHeader eyebrow="Conta" title="Segurança da conta" description="Troque sua senha e encerre todas as sessões ativas." />
      <Card title="Alterar senha" description="Após a troca, será necessário entrar novamente em cada dispositivo.">
        <form className="vn-form" onSubmit={submit}>
          <Input label="Senha atual" type="password" autoComplete="current-password" value={currentPassword} onChange={(event) => setCurrentPassword(event.target.value)} required />
          <Input label="Nova senha" type="password" autoComplete="new-password" minLength={8} value={newPassword} onChange={(event) => setNewPassword(event.target.value)} required />
          <Input label="Confirmar nova senha" type="password" autoComplete="new-password" minLength={8} value={confirmation} onChange={(event) => setConfirmation(event.target.value)} required />
          {(validationError || apiError) && <p className="vn-error" role="alert">{validationError || apiError?.message}</p>}
          <Button type="submit" disabled={change.isPending}>{change.isPending ? 'Atualizando...' : 'Alterar senha'}</Button>
        </form>
      </Card>
    </section>
  );
}
