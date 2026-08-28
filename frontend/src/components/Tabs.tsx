import type { ReactNode } from 'react';
import { useState } from 'react';

type Tab = { id: string; label: string; content: ReactNode };

export function Tabs({ tabs, active, onChange }: { tabs: Tab[]; active?: string; onChange?: (id: string) => void }) {
  const [internalActive, setInternalActive] = useState(tabs[0]?.id ?? '');
  const currentId = active ?? internalActive;
  const current = tabs.find((tab) => tab.id === currentId) ?? tabs[0];

  function handleChange(id: string) {
    if (!active) setInternalActive(id);
    onChange?.(id);
  }

  return (
    <div className="vn-tabs">
      <div className="vn-tabs__list" role="tablist">
        {tabs.map((tab) => <button key={tab.id} className={tab.id === current.id ? 'active' : ''} onClick={() => handleChange(tab.id)}>{tab.label}</button>)}
      </div>
      <div className="vn-tabs__panel">{current?.content}</div>
    </div>
  );
}
