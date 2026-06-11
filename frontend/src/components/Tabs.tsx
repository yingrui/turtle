import type { ReactNode } from 'react';

type Tab = { id: string; label: string };

export function Tabs({
  tabs,
  active,
  onChange,
  children,
}: {
  tabs: Tab[];
  active: string;
  onChange: (id: string) => void;
  children: ReactNode;
}) {
  return (
    <div>
      <div className="tabs">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            type="button"
            className={`tabs__btn${active === tab.id ? ' tabs__btn--active' : ''}`}
            onClick={() => onChange(tab.id)}
          >
            {tab.label}
          </button>
        ))}
      </div>
      <div className="tabs__panel">{children}</div>
    </div>
  );
}
