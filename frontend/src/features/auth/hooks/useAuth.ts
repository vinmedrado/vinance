import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useSyncExternalStore } from 'react';
import { getAccessToken, getSessionVersion, isAccessTokenExpired, subscribeToSession } from '../../../services/api';
import { changePassword, getMe, login, logout, register, restoreSession } from '../services/auth.service';

export function useSessionToken() {
  return useSyncExternalStore(subscribeToSession, getAccessToken, () => null);
}

function useSessionVersion() {
  return useSyncExternalStore(subscribeToSession, getSessionVersion, () => 0);
}

const authUserQueryKey = (version: number) => ['auth', 'me', version] as const;

export function useCurrentUser() {
  const token = useSessionToken();
  const version = useSessionVersion();
  return useQuery({
    queryKey: authUserQueryKey(version),
    queryFn: ({ signal }) => token && !isAccessTokenExpired(token) ? getMe(signal) : restoreSession(),
    retry: false,
    staleTime: 5 * 60_000,
    refetchOnMount: false,
    refetchOnWindowFocus: true,
  });
}

export function useLogin() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: login,
    onSuccess: (data) => queryClient.setQueryData(authUserQueryKey(getSessionVersion()), data.user),
  });
}

export function useRegister() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: register,
    onSuccess: (data) => queryClient.setQueryData(authUserQueryKey(getSessionVersion()), data.user),
  });
}

export function useChangePassword() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: changePassword,
    onSuccess: () => queryClient.clear(),
  });
}

export function useLogout() {
  const queryClient = useQueryClient();
  return async () => {
    await queryClient.cancelQueries();
    await logout();
    queryClient.clear();
  };
}
