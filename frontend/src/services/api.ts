import axios, { AxiosError } from 'axios';

const RAW_API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000';
export const API_BASE_URL = RAW_API_BASE_URL.replace(/\/$/, '');
const API_PREFIX = import.meta.env.VITE_API_PREFIX ?? '/api/v1';

const ACCESS_TOKEN_KEY = 'vinance_access_token';
const USER_KEY = 'vinance_user';
const SESSION_CHANGE_EVENT = 'vinance:session-change';

export type SessionChangeReason = 'login' | 'logout' | 'expired' | 'invalid' | 'storage';

let lastSessionChangeReason: SessionChangeReason | null = null;

export type ApiErrorShape = {
  status: number;
  message: string;
  code?: string;
  correlationId?: string;
};

export class ApiRequestError extends Error implements ApiErrorShape {
  status: number;
  code?: string;
  correlationId?: string;

  constructor(status: number, message: string, code?: string, correlationId?: string) {
    super(message);
    this.name = 'ApiRequestError';
    this.status = status;
    this.code = code;
    this.correlationId = correlationId;
  }
}

function emitSessionChange(reason: SessionChangeReason) {
  lastSessionChangeReason = reason;
  if (typeof window !== 'undefined') {
    window.dispatchEvent(new CustomEvent(SESSION_CHANGE_EVENT, { detail: { reason } }));
  }
}

function requestBearerToken(error: AxiosError) {
  const authorization = error.config?.headers?.Authorization;
  if (typeof authorization !== 'string') return null;
  return authorization.replace(/^Bearer\s+/i, '').trim() || null;
}

function errorDetail(error: AxiosError<{ detail?: string | Array<{ msg?: string }>; error?: string }>) {
  const detail = error.response?.data?.detail;
  if (Array.isArray(detail)) return detail.map((item) => item.msg).filter(Boolean).join(' | ');
  if (typeof detail === 'string') return detail;
  return typeof error.response?.data?.error === 'string' ? error.response.data.error : '';
}

function correlationId(error: AxiosError) {
  const value = error.response?.headers?.['x-correlation-id'] ?? error.config?.headers?.['X-Correlation-ID'];
  const normalized = typeof value === 'string' ? value.trim().toLowerCase() : '';
  return /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/.test(normalized)
    ? normalized
    : undefined;
}

export function normalizeApiError(error: unknown): ApiRequestError {
  if (error instanceof ApiRequestError) return error;
  if (!axios.isAxiosError(error)) {
    return new ApiRequestError(0, error instanceof Error ? error.message : 'Falha inesperada na integração.', 'UNKNOWN');
  }

  const typedError = error as AxiosError<{ detail?: string | Array<{ msg?: string }>; error?: string }>;
  const status = typedError.response?.status ?? 0;
  const canceled = axios.isCancel(typedError) || typedError.code === 'ERR_CANCELED';
  const timedOut = typedError.code === 'ECONNABORTED' || typedError.code === 'ETIMEDOUT';
  const detail = errorDetail(typedError);
  const message = canceled
    ? 'A solicitação foi cancelada.'
    : timedOut
    ? 'A solicitação excedeu o tempo limite. Tente novamente.'
    : status === 0
      ? 'API offline ou indisponível no momento.'
      : detail || typedError.message || 'Não foi possível se comunicar com a API.';
  const code = canceled ? 'REQUEST_CANCELED' : timedOut ? 'TIMEOUT' : status === 401 ? 'AUTH_EXPIRED' : status === 0 ? 'NETWORK_ERROR' : undefined;

  return new ApiRequestError(status, message, code, correlationId(typedError));
}

export const api = axios.create({
  baseURL: `${API_BASE_URL}${API_PREFIX}`,
  timeout: 15000,
  headers: { 'Content-Type': 'application/json' },
});

api.interceptors.request.use((config) => {
  const token = getAccessToken();
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

api.interceptors.response.use(
  (response) => response,
  (error: AxiosError<{ detail?: string | Array<{ msg?: string }>; error?: string }>) => {
    const normalized = normalizeApiError(error);

    if (normalized.status === 401) {
      const requestToken = requestBearerToken(error);
      const currentToken = getAccessToken();
      if (requestToken && requestToken === currentToken) clearSession('invalid');
    }
    return Promise.reject(normalized);
  },
);

export function getAccessToken() {
  return typeof window === 'undefined' ? null : window.localStorage.getItem(ACCESS_TOKEN_KEY);
}

export function setSession(token: string, user: unknown) {
  window.localStorage.setItem(ACCESS_TOKEN_KEY, token);
  window.localStorage.setItem(USER_KEY, JSON.stringify(user));
  emitSessionChange('login');
}

export function getStoredUser<T>() {
  if (typeof window === 'undefined') return null;
  const value = window.localStorage.getItem(USER_KEY);
  if (!value) return null;
  try { return JSON.parse(value) as T; } catch { return null; }
}

export function clearSession(reason: SessionChangeReason = 'logout') {
  if (typeof window === 'undefined') return;
  window.localStorage.removeItem(ACCESS_TOKEN_KEY);
  window.localStorage.removeItem(USER_KEY);
  emitSessionChange(reason);
}

export function subscribeToSession(onStoreChange: () => void) {
  if (typeof window === 'undefined') return () => undefined;

  const handleSessionChange = (event: Event) => {
    const reason = (event as CustomEvent<{ reason?: SessionChangeReason }>).detail?.reason;
    if (reason) lastSessionChangeReason = reason;
    onStoreChange();
  };
  const handleStorage = (event: StorageEvent) => {
    if (event.key !== ACCESS_TOKEN_KEY && event.key !== USER_KEY) return;
    lastSessionChangeReason = 'storage';
    onStoreChange();
  };

  window.addEventListener(SESSION_CHANGE_EVENT, handleSessionChange);
  window.addEventListener('storage', handleStorage);
  return () => {
    window.removeEventListener(SESSION_CHANGE_EVENT, handleSessionChange);
    window.removeEventListener('storage', handleStorage);
  };
}

export function getLastSessionChangeReason() {
  return lastSessionChangeReason;
}

function decodeTokenPayload(token: string) {
  try {
    const payload = token.split('.')[1];
    if (!payload) return null;
    const normalized = payload.replace(/-/g, '+').replace(/_/g, '/').padEnd(Math.ceil(payload.length / 4) * 4, '=');
    return JSON.parse(atob(normalized)) as { exp?: unknown };
  } catch {
    return null;
  }
}

export function getAccessTokenExpiration(token = getAccessToken()) {
  if (!token) return null;
  const expiration = decodeTokenPayload(token)?.exp;
  return typeof expiration === 'number' && Number.isFinite(expiration) ? expiration * 1000 : null;
}

export function isAccessTokenExpired(token = getAccessToken(), now = Date.now()) {
  const expiration = getAccessTokenExpiration(token);
  return expiration !== null && expiration <= now;
}

export function isAuthenticated() {
  const token = getAccessToken();
  return Boolean(token && !isAccessTokenExpired(token));
}

// Legacy compatibility helpers kept for archived pages still compiled by TypeScript.
export async function login(email: string, password: string) {
  const { data } = await api.post('/auth/login', { email, password });
  const token = data?.access_token ?? data?.token;
  if (token) setSession(token, data?.user ?? { email });
  return data;
}

export async function register(payload: { email: string; password: string; full_name?: string; organization_name?: string }) {
  const { data } = await api.post('/auth/register', payload);
  const token = data?.access_token ?? data?.token;
  if (token) setSession(token, data?.user ?? { email: payload.email });
  return data;
}
