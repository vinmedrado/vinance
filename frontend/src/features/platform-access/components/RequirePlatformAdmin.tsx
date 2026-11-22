import type { ReactElement } from 'react';
import { Navigate } from 'react-router-dom';
import { usePlatformAccessProfile } from '../hooks/usePlatformAccess';

export function RequirePlatformAdmin({ children }: { children: ReactElement }) {
  const { isPlatformAdmin, isLoading } = usePlatformAccessProfile();
  if (isLoading) return <div className="vn-route-loading" role="status">Validando permissão administrativa…</div>;
  return isPlatformAdmin ? children : <Navigate to="/dashboard" replace />;
}
