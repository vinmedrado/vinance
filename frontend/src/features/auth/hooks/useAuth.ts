import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useSyncExternalStore } from 'react';
import { getAccessToken, isAccessTokenExpired, subscribeToSession } from '../../../services/api';
import { getMe, login, logout, register } from '../services/auth.service';

export function useSessionToken() {
  return useSyncExternalStore(subscribeToSession, getAccessToken, () => null);
}

const authUserQueryKey = (token: string | null) => ['auth', 'me', token] as const;

export function useCurrentUser() {
  const token = useSessionToken();
  return useQuery({
    queryKey: authUserQueryKey(token),
    queryFn: ({ signal }) => getMe(signal),
    enabled: Boolean(token && !isAccessTokenExpired(token)),
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
    onSuccess: (data) => queryClient.setQueryData(authUserQueryKey(data.access_token), data.user),
  });
}

export function useRegister() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: register,
    onSuccess: (data) => queryClient.setQueryData(authUserQueryKey(data.access_token), data.user),
  });
}

export function useLogout() {
  const queryClient = useQueryClient();
  return async () => {
    await queryClient.cancelQueries();
    logout();
    queryClient.clear();
  };
}
