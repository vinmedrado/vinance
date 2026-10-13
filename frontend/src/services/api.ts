import axios, { AxiosError, InternalAxiosRequestConfig } from 'axios';

const RAW_API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? '';
export const API_BASE_URL = RAW_API_BASE_URL.replace(/\/$/, '');
const API_PREFIX = import.meta.env.VITE_API_PREFIX ?? '/api/v1';
const SESSION_CHANGE_EVENT = 'vinance:session-change';
const API_ROOT = `${API_BASE_URL}${API_PREFIX}`;

export type SessionChangeReason = 'login' | 'logout' | 'expired' | 'invalid' | 'storage';

let lastSessionChangeReason: SessionChangeReason | null = null;
let accessToken: string | null = null;
let currentUser: unknown = null;
let refreshPromise: Promise<string | null> | null = null;
let sessionVersion = 0;

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
  sessionVersion += 1;
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
  baseURL: API_ROOT,
  timeout: 15000,
  withCredentials: true,
  headers: { 'Content-Type': 'application/json' },
});

const sessionApi = axios.create({
  baseURL: API_ROOT,
  timeout: 15000,
  withCredentials: true,
  headers: { 'Content-Type': 'application/json', 'X-Requested-With': 'XMLHttpRequest' },
});

api.interceptors.request.use((config) => {
  const token = getAccessToken();
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

type RetryableRequest = InternalAxiosRequestConfig & { _sessionRetry?: boolean };

function isSessionEndpoint(url?: string) {
  return Boolean(url && /\/(?:login|register|refresh|logout)(?:\?|$)/.test(url));
}

export async function refreshSession() {
  if (!refreshPromise) {
    const hadAccessToken = Boolean(accessToken);
    refreshPromise = sessionApi.post<unknown>('/refresh')
      .then(({ data }) => {
        if (!data || typeof data !== 'object') throw new Error('Invalid refresh response');
        const record = data as Record<string, unknown>;
        const token = typeof record.access_token === 'string' ? record.access_token.trim() : '';
        if (!token) throw new Error('Invalid refresh token response');
        setSession(token, record.user, 'login');
        return token;
      })
      .catch((error: unknown) => {
        const normalized = normalizeApiError(error);
        if (normalized.status === 401) {
          if (hadAccessToken) clearSession('invalid');
          return null;
        }
        throw normalized;
      })
      .finally(() => { refreshPromise = null; });
  }
  return refreshPromise;
}

api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError<{ detail?: string | Array<{ msg?: string }>; error?: string }>) => {
    const original = error.config as RetryableRequest | undefined;
    if (error.response?.status === 401 && original && !original._sessionRetry && !isSessionEndpoint(original.url)) {
      original._sessionRetry = true;
      const token = await refreshSession().catch(() => null);
      if (token) {
        original.headers.Authorization = `Bearer ${token}`;
        return api.request(original);
      }
    }
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
  return accessToken;
}

export function setSession(token: string, user: unknown, reason: SessionChangeReason = 'login') {
  accessToken = token;
  currentUser = user;
  emitSessionChange(reason);
}

export function getStoredUser<T>() {
  return currentUser as T | null;
}

export function clearSession(reason: SessionChangeReason = 'logout') {
  accessToken = null;
  currentUser = null;
  emitSessionChange(reason);
}

export function subscribeToSession(onStoreChange: () => void) {
  if (typeof window === 'undefined') return () => undefined;

  const handleSessionChange = (event: Event) => {
    const reason = (event as CustomEvent<{ reason?: SessionChangeReason }>).detail?.reason;
    if (reason) lastSessionChangeReason = reason;
    onStoreChange();
  };
  window.addEventListener(SESSION_CHANGE_EVENT, handleSessionChange);
  return () => {
    window.removeEventListener(SESSION_CHANGE_EVENT, handleSessionChange);
  };
}

export function getLastSessionChangeReason() {
  return lastSessionChangeReason;
}

export function getSessionVersion() {
  return sessionVersion;
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
