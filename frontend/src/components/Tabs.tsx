import type { KeyboardEvent, ReactNode } from 'react';
import { useId, useState } from 'react';

type Tab = { id: string; label: string; content: ReactNode };

export function Tabs({ tabs, active, onChange }: { tabs: Tab[]; active?: string; onChange?: (id: string) => void }) {
  const instanceId = useId().replace(/:/g, '');
  const [internalActive, setInternalActive] = useState(tabs[0]?.id ?? '');
  const currentId = active ?? internalActive;
  const current = tabs.find((tab) => tab.id === currentId) ?? tabs[0];

  function handleChange(id: string) {
    if (active === undefined) setInternalActive(id);
    onChange?.(id);
  }

  function handleKeyDown(event: KeyboardEvent<HTMLButtonElement>, index: number) {
    if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
    event.preventDefault();
    const lastIndex = tabs.length - 1;
    const nextIndex = event.key === 'Home'
      ? 0
      : event.key === 'End'
        ? lastIndex
        : event.key === 'ArrowRight'
          ? (index + 1) % tabs.length
          : (index - 1 + tabs.length) % tabs.length;
    handleChange(tabs[nextIndex].id);
    const buttons = event.currentTarget.parentElement?.querySelectorAll<HTMLButtonElement>('[role="tab"]');
    buttons?.[nextIndex]?.focus();
  }

  return (
    <div className="vn-tabs">
      <div className="vn-tabs__list" role="tablist" aria-label="Classes de mercado">
        {tabs.map((tab, index) => {
          const selected = tab.id === current?.id;
          return <button
            key={tab.id}
            id={`${instanceId}-tab-${tab.id}`}
            type="button"
            role="tab"
            aria-selected={selected}
            aria-controls={`${instanceId}-panel-${tab.id}`}
            tabIndex={selected ? 0 : -1}
            className={selected ? 'active' : ''}
            onClick={() => handleChange(tab.id)}
            onKeyDown={(event) => handleKeyDown(event, index)}
          >{tab.label}</button>;
        })}
      </div>
      {current && <div
        className="vn-tabs__panel"
        id={`${instanceId}-panel-${current.id}`}
        role="tabpanel"
        aria-labelledby={`${instanceId}-tab-${current.id}`}
      >{current.content}</div>}
    </div>
  );
}
