import { api, ApiRequestError, clearSession, getStoredUser, setSession } from '../../../services/api';
import type { LoginPayload, RegisterPayload, TokenResponse, User } from '../types/auth.types';

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function normalizeUser(value: unknown): User {
  if (!isRecord(value)
    || typeof value.id !== 'number'
    || !Number.isFinite(value.id)
    || typeof value.email !== 'string'
    || !value.email.trim()
    || typeof value.is_active !== 'boolean') {
    throw new ApiRequestError(502, 'A API retornou uma sessão de usuário inválida.', 'INVALID_RESPONSE');
  }
  return {
    id: value.id,
    email: value.email.trim(),
    full_name: typeof value.full_name === 'string' ? value.full_name.trim() || null : null,
    is_active: value.is_active,
  };
}

function normalizeTokenResponse(value: unknown): TokenResponse {
  if (!isRecord(value) || typeof value.access_token !== 'string' || !value.access_token.trim()) {
    throw new ApiRequestError(502, 'A API retornou uma autenticação inválida.', 'INVALID_RESPONSE');
  }
  return {
    access_token: value.access_token.trim(),
    token_type: typeof value.token_type === 'string' && value.token_type.trim() ? value.token_type.trim() : 'bearer',
    user: normalizeUser(value.user),
  };
}

export async function login(payload: LoginPayload) {
  const { data } = await api.post<unknown>('/login', payload);
  const session = normalizeTokenResponse(data);
  setSession(session.access_token, session.user);
  return session;
}

export async function register(payload: RegisterPayload) {
  const { data } = await api.post<unknown>('/register', payload);
  const session = normalizeTokenResponse(data);
  setSession(session.access_token, session.user);
  return session;
}

export async function getMe(signal?: AbortSignal) {
  const { data } = await api.get<unknown>('/me', { signal });
  return normalizeUser(data);
}

export function logout() { clearSession(); }
export function getCurrentStoredUser() { return getStoredUser<User>(); }
