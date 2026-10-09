import { api } from '../../../services/api';
import type {
  CreateHouseholdPayload,
  CreateInvitationPayload,
  Household,
  HouseholdInvitation,
  HouseholdMember,
  HouseholdRole,
} from '../types/household.types';

export async function listHouseholds(signal?: AbortSignal) {
  const { data } = await api.get<Household[]>('/financial/households', { signal });
  return data;
}

export async function getDefaultHousehold(signal?: AbortSignal) {
  const { data } = await api.get<Household>('/financial/households/default', { signal });
  return data;
}

export async function createHousehold(payload: CreateHouseholdPayload) {
  const { data } = await api.post<Household>('/financial/households', payload);
  return data;
}

export async function listMembers(householdId: number, signal?: AbortSignal) {
  const { data } = await api.get<HouseholdMember[]>(
    `/financial/households/${householdId}/members`,
    { signal },
  );
  return data;
}

export async function updateMemberRole(
  householdId: number,
  memberId: number,
  role: HouseholdRole,
) {
  const { data } = await api.patch<HouseholdMember>(
    `/financial/households/${householdId}/members/${memberId}`,
    { role },
  );
  return data;
}

export async function removeMember(householdId: number, memberId: number) {
  await api.delete(`/financial/households/${householdId}/members/${memberId}`);
}

export async function leaveHousehold(householdId: number) {
  await api.post(`/financial/households/${householdId}/leave`);
}

export async function setDefaultHousehold(householdId: number) {
  const { data } = await api.post<Household>(`/financial/households/${householdId}/default`);
  return data;
}

export async function listHouseholdInvitations(householdId: number, signal?: AbortSignal) {
  const { data } = await api.get<HouseholdInvitation[]>(
    `/financial/households/${householdId}/invitations`,
    { signal },
  );
  return data;
}

export async function listIncomingInvitations(signal?: AbortSignal) {
  const { data } = await api.get<HouseholdInvitation[]>(
    '/financial/household-invitations',
    { signal },
  );
  return data;
}

export async function createInvitation(householdId: number, payload: CreateInvitationPayload) {
  const { data } = await api.post<HouseholdInvitation>(
    `/financial/households/${householdId}/invitations`,
    payload,
  );
  return data;
}

export async function cancelInvitation(householdId: number, invitationId: number) {
  const { data } = await api.post<HouseholdInvitation>(
    `/financial/households/${householdId}/invitations/${invitationId}/cancel`,
  );
  return data;
}

export async function acceptInvitation(invitationId: number) {
  const { data } = await api.post<HouseholdInvitation>(
    `/financial/household-invitations/${invitationId}/accept`,
  );
  return data;
}

export async function declineInvitation(invitationId: number) {
  const { data } = await api.post<HouseholdInvitation>(
    `/financial/household-invitations/${invitationId}/decline`,
  );
  return data;
}
