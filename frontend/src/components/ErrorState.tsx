import { AlertTriangle } from 'lucide-react';
import type { ReactNode } from 'react';

export function ErrorState({ title = 'Não foi possível concluir a ação', description, action }: { title?: string; description: string; action?: ReactNode }) {
  return (
    <div className="vn-error-state" role="alert">
      <div className="vn-error-state__mark"><AlertTriangle size={22} aria-hidden="true" /></div>
      <div><h3>{title}</h3><p>{description}</p></div>
      {action && <div>{action}</div>}
    </div>
  );
}
