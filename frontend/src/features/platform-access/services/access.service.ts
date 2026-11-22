import { api, setSession } from '../../../services/api';
import type { TokenResponse } from '../../auth/types/auth.types';
import type {
  AccessCapabilities,
  CredentialRegistration,
  InvitationIssued,
  PlatformAccessProfile,
  PlatformInvitation,
  PlatformUser,
} from '../types/access.types';

export async function getAccessCapabilities() {
  const { data } = await api.get<AccessCapabilities>('/access/capabilities');
  return data;
}

export async function getPlatformAccessProfile() {
  const { data } = await api.get<PlatformAccessProfile>('/access/profile');
  return data;
}

function acceptSession(data: TokenResponse) {
  setSession(data.access_token, data.user);
  return data;
}

export async function bootstrapAccount(payload: CredentialRegistration & { bootstrap_credential: string }) {
  const { data } = await api.post<TokenResponse>('/access/bootstrap', payload);
  return acceptSession(data);
}

export async function acceptPlatformInvitation(payload: CredentialRegistration & { token: string }) {
  const { data } = await api.post<TokenResponse>('/access/invitations/accept', payload);
  return acceptSession(data);
}

export async function requestPasswordRecovery(email: string) {
  const { data } = await api.post<{ accepted: boolean; delivery_available: boolean; message: string }>(
    '/access/password-recovery/request', { email },
  );
  return data;
}

export async function completePasswordRecovery(payload: { token: string; new_password: string; password_confirmation: string }) {
  const { data } = await api.post<{ status: string; message: string }>('/access/password-recovery/complete', payload);
  return data;
}

export async function listPlatformUsers() {
  const { data } = await api.get<PlatformUser[]>('/access/admin/users');
  return data;
}

export async function listPlatformInvitations() {
  const { data } = await api.get<PlatformInvitation[]>('/access/admin/invitations');
  return data;
}

export async function createPlatformInvitation(email: string) {
  const { data } = await api.post<InvitationIssued>('/access/admin/invitations', { email });
  return data;
}

export async function resendPlatformInvitation(id: string) {
  const { data } = await api.post<InvitationIssued>(`/access/admin/invitations/${id}/resend`);
  return data;
}

export async function cancelPlatformInvitation(id: string) {
  const { data } = await api.post<PlatformInvitation>(`/access/admin/invitations/${id}/cancel`);
  return data;
}

export async function setPlatformUserActive(userId: number, active: boolean) {
  const action = active ? 'activate' : 'deactivate';
  const { data } = await api.post<{ status: string; message: string }>(`/access/admin/users/${userId}/${action}`);
  return data;
}

export async function issuePasswordResetLink(userId: number) {
  const { data } = await api.post<{ reset_path: string; expires_at: string; message: string }>(
    `/access/admin/users/${userId}/password-reset-link`,
  );
  return data;
}

export function takeTokenFromFragment(): string | null {
  if (typeof window === 'undefined') return null;
  const params = new URLSearchParams(window.location.hash.replace(/^#/, ''));
  const token = params.get('token')?.trim() || null;
  if (window.location.hash) {
    window.history.replaceState(window.history.state, '', `${window.location.pathname}${window.location.search}`);
  }
  return token;
}
