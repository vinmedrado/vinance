import { useEffect } from 'react';
import type { ReactElement } from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { Button, Card, ErrorState, LoadingState } from '../../../components';
import {
  clearSession,
  getAccessTokenExpiration,
  getLastSessionChangeReason,
  isAccessTokenExpired,
  type ApiErrorShape,
} from '../../../services/api';
import { useCurrentUser, useSessionToken } from '../hooks/useAuth';

function returnPath(pathname: string, search: string, hash: string) {
  return `${pathname}${search}${hash}`;
}

export function RequireAuth({ children }: { children: ReactElement }) {
  const location = useLocation();
  const token = useSessionToken();
  const session = useCurrentUser();
  const expired = Boolean(token && isAccessTokenExpired(token));
  const expiration = getAccessTokenExpiration(token);
  const error = session.error as ApiErrorShape | null;
  const from = returnPath(location.pathname, location.search, location.hash);

  useEffect(() => {
    if (!token || expiration === null) return;
    let timer: number | undefined;
    const scheduleExpiration = () => {
      const remaining = expiration - Date.now();
      if (remaining <= 0) {
        clearSession('expired');
        return;
      }
      timer = window.setTimeout(scheduleExpiration, Math.min(remaining, 2_147_483_647));
    };
    scheduleExpiration();
    return () => {
      if (timer !== undefined) window.clearTimeout(timer);
    };
  }, [expiration, token]);

  useEffect(() => {
    if (token && (error?.code === 'AUTH_EXPIRED' || error?.status === 401)) clearSession('invalid');
  }, [error?.code, error?.status, token]);

  if (!token || expired || error?.code === 'AUTH_EXPIRED' || error?.status === 401) {
    const lastReason = getLastSessionChangeReason();
    const reason = expired || lastReason === 'expired' ? 'expired' : error?.status === 401 || lastReason === 'invalid' ? 'invalid' : 'required';
    return <Navigate to="/login" replace state={{ from, reason }} />;
  }

  if (!session.data && session.isFetching) {
    return (
      <main className="vn-auth-gate" aria-label="Validação da sessão">
        <Card><LoadingState label="Validando sua sessão com o Vinance..." /></Card>
      </main>
    );
  }

  if (error || !session.data) {
    return (
      <main className="vn-auth-gate">
        <Card>
          <ErrorState
            title="Não foi possível validar sua sessão"
            description={error?.message ?? 'A autenticação não pôde ser confirmada agora.'}
            action={(
              <div className="vn-inline-actions">
                <Button variant="secondary" onClick={() => session.refetch()}>Tentar novamente</Button>
                <Button variant="ghost" onClick={() => clearSession('logout')}>Voltar para o login</Button>
              </div>
            )}
          />
        </Card>
      </main>
    );
  }

  return children;
}
