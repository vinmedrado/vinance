import type { PropsWithChildren } from 'react';

export function Badge({ children, tone = 'neutral' }: PropsWithChildren<{ tone?: 'neutral' | 'success' | 'warning' | 'danger' }>) {
  return <span className={`vn-badge vn-badge--${tone}`}>{children}</span>;
}
