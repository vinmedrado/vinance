import type { ReactNode } from 'react';

export function EmptyState({ title, description, action }: { title: string; description: string; action?: ReactNode }) {
  return <div className="vn-empty"><div className="vn-empty__mark">◦</div><h3>{title}</h3><p>{description}</p>{action}</div>;
}
