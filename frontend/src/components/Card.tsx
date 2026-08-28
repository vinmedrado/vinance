import type { PropsWithChildren, ReactNode } from 'react';

type CardProps = PropsWithChildren<{ title?: string; description?: string; action?: ReactNode; className?: string }>;

export function Card({ title, description, action, className = '', children }: CardProps) {
  return (
    <section className={`vn-card ${className}`.trim()}>
      {(title || description || action) && (
        <div className="vn-card__header">
          <div>
            {title && <h3>{title}</h3>}
            {description && <p>{description}</p>}
          </div>
          {action}
        </div>
      )}
      {children}
    </section>
  );
}
