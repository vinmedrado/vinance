import type { ReactNode } from 'react';
import { Badge } from './Badge';
import { Card } from './Card';

type MetricCardProps = {
  label: string;
  value: ReactNode;
  helper?: string;
  badge?: string;
  tone?: 'neutral' | 'success' | 'warning' | 'danger';
  icon?: ReactNode;
};

export function MetricCard({ label, value, helper, badge, tone = 'neutral', icon }: MetricCardProps) {
  return (
    <Card className="vn-metric-card">
      <div className="vn-metric-card__top">
        <span>{label}</span>
        {icon}
      </div>
      <strong>{value}</strong>
      <div className="vn-metric-card__footer">
        {helper && <small>{helper}</small>}
        {badge && <Badge tone={tone}>{badge}</Badge>}
      </div>
    </Card>
  );
}
