import type { ReactNode } from 'react';

type SectionHeaderProps = {
  eyebrow?: string;
  title: string;
  description?: string;
  action?: ReactNode;
  headingLevel?: 1 | 2;
};

export function SectionHeader({ eyebrow, title, description, action, headingLevel = 2 }: SectionHeaderProps) {
  const Heading = headingLevel === 1 ? 'h1' : 'h2';
  return (
    <div className="vn-section-header">
      <div>
        {eyebrow && <span className="vn-kicker">{eyebrow}</span>}
        <Heading>{title}</Heading>
        {description && <p>{description}</p>}
      </div>
      {action && <div className="vn-section-header__action">{action}</div>}
    </div>
  );
}
