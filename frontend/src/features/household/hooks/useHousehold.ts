import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useSessionToken } from '../../auth/hooks/useAuth';
import {
  acceptInvitation,
  cancelInvitation,
  createHousehold,
  createInvitation,
  declineInvitation,
  getDefaultHousehold,
  leaveHousehold,
  listHouseholdInvitations,
  listHouseholds,
  listIncomingInvitations,
  listMembers,
  removeMember,
  setDefaultHousehold,
  updateMemberRole,
} from '../services/household.service';
import type { CreateInvitationPayload, HouseholdRole } from '../types/household.types';

export const householdQueryKey = (token: string | null, ...parts: Array<string | number | null>) =>
  ['household', token, ...parts] as const;

type ScopedRequest<T = undefined> = {
  householdId: number;
  sessionToken: string | null;
  payload: T;
};

function assertSession(expected: string | null, current: string | null) {
  if (expected !== current) throw new Error('A sessão mudou. Revise a ação antes de continuar.');
}

export function useHouseholdList() {
  const token = useSessionToken();
  return useQuery({
    queryKey: householdQueryKey(token, 'list'),
    queryFn: ({ signal }) => listHouseholds(signal),
  });
}

export function useHouseholdDefault() {
  const token = useSessionToken();
  return useQuery({
    queryKey: householdQueryKey(token, 'default'),
    queryFn: ({ signal }) => getDefaultHousehold(signal),
  });
}

export function useHouseholdMembers(householdId: number | null) {
  const token = useSessionToken();
  return useQuery({
    queryKey: householdQueryKey(token, householdId, 'members'),
    queryFn: ({ signal }) => listMembers(householdId as number, signal),
    enabled: householdId !== null,
  });
}

export function useIncomingInvitations() {
  const token = useSessionToken();
  return useQuery({
    queryKey: householdQueryKey(token, 'incoming-invitations'),
    queryFn: ({ signal }) => listIncomingInvitations(signal),
  });
}

export function useOutgoingInvitations(householdId: number | null, enabled: boolean) {
  const token = useSessionToken();
  return useQuery({
    queryKey: householdQueryKey(token, householdId, 'invitations'),
    queryFn: ({ signal }) => listHouseholdInvitations(householdId as number, signal),
    enabled: householdId !== null && enabled,
  });
}

function useInvalidateHouseholds() {
  const client = useQueryClient();
  return (token: string | null, householdId?: number) => {
    client.invalidateQueries({ queryKey: householdQueryKey(token, 'list') });
    client.invalidateQueries({ queryKey: householdQueryKey(token, 'default') });
    client.invalidateQueries({ queryKey: householdQueryKey(token, 'incoming-invitations') });
    if (householdId !== undefined) {
      client.invalidateQueries({ queryKey: householdQueryKey(token, householdId, 'members') });
      client.invalidateQueries({ queryKey: householdQueryKey(token, householdId, 'invitations') });
    }
    client.invalidateQueries({ queryKey: ['financial-state', token, 'households'] });
    client.invalidateQueries({ queryKey: ['financial-state', token, 'household', 'default'] });
  };
}

export function useCreateHousehold() {
  const currentToken = useSessionToken();
  const client = useQueryClient();
  const invalidate = useInvalidateHouseholds();
  return useMutation({
    mutationFn: (request: ScopedRequest<{ name: string }>) => {
      assertSession(request.sessionToken, currentToken);
      return createHousehold({ name: request.payload.name, household_type: 'SHARED' });
    },
    onSuccess: (data, request) => {
      client.setQueryData<Awaited<ReturnType<typeof listHouseholds>>>(
        householdQueryKey(request.sessionToken, 'list'),
        (current = []) => current.some((item) => item.id === data.id) ? current : [...current, data],
      );
      invalidate(request.sessionToken);
    },
  });
}

export function useCreateInvitation() {
  const currentToken = useSessionToken();
  const invalidate = useInvalidateHouseholds();
  return useMutation({
    mutationFn: (request: ScopedRequest<CreateInvitationPayload>) => {
      assertSession(request.sessionToken, currentToken);
      return createInvitation(request.householdId, request.payload);
    },
    onSuccess: (_data, request) => invalidate(request.sessionToken, request.householdId),
  });
}

export function useInvitationDecision(action: 'accept' | 'decline') {
  const currentToken = useSessionToken();
  const invalidate = useInvalidateHouseholds();
  return useMutation({
    mutationFn: (request: { invitationId: number; sessionToken: string | null }) => {
      assertSession(request.sessionToken, currentToken);
      return action === 'accept'
        ? acceptInvitation(request.invitationId)
        : declineInvitation(request.invitationId);
    },
    onSuccess: (data, request) => invalidate(request.sessionToken, data.household_id),
  });
}

export function useCancelInvitation() {
  const currentToken = useSessionToken();
  const invalidate = useInvalidateHouseholds();
  return useMutation({
    mutationFn: (request: ScopedRequest<{ invitationId: number }>) => {
      assertSession(request.sessionToken, currentToken);
      return cancelInvitation(request.householdId, request.payload.invitationId);
    },
    onSuccess: (_data, request) => invalidate(request.sessionToken, request.householdId),
  });
}

export function useUpdateMemberRole() {
  const currentToken = useSessionToken();
  const invalidate = useInvalidateHouseholds();
  return useMutation({
    mutationFn: (request: ScopedRequest<{ memberId: number; role: HouseholdRole }>) => {
      assertSession(request.sessionToken, currentToken);
      return updateMemberRole(request.householdId, request.payload.memberId, request.payload.role);
    },
    onSuccess: (_data, request) => invalidate(request.sessionToken, request.householdId),
  });
}

export function useRemoveMember() {
  const currentToken = useSessionToken();
  const invalidate = useInvalidateHouseholds();
  return useMutation({
    mutationFn: (request: ScopedRequest<{ memberId: number }>) => {
      assertSession(request.sessionToken, currentToken);
      return removeMember(request.householdId, request.payload.memberId);
    },
    onSuccess: (_data, request) => invalidate(request.sessionToken, request.householdId),
  });
}

export function useSetDefaultHousehold() {
  const currentToken = useSessionToken();
  const invalidate = useInvalidateHouseholds();
  return useMutation({
    mutationFn: (request: ScopedRequest) => {
      assertSession(request.sessionToken, currentToken);
      return setDefaultHousehold(request.householdId);
    },
    onSuccess: (_data, request) => invalidate(request.sessionToken, request.householdId),
  });
}

export function useLeaveHousehold() {
  const currentToken = useSessionToken();
  const invalidate = useInvalidateHouseholds();
  return useMutation({
    mutationFn: (request: ScopedRequest) => {
      assertSession(request.sessionToken, currentToken);
      return leaveHousehold(request.householdId);
    },
    onSuccess: (_data, request) => invalidate(request.sessionToken, request.householdId),
  });
}
