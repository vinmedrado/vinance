import type { ReactNode } from 'react';

export function FormField({ label, helper, children }: { label: string; helper?: string; children: ReactNode }) {
  return (
    <label className="vn-field">
      <span>{label}</span>
      {children}
      {helper && <small>{helper}</small>}
    </label>
  );
}
