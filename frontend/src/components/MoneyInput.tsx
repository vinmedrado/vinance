import type { InputHTMLAttributes } from 'react';

export function MoneyInput({ label, helper, ...props }: InputHTMLAttributes<HTMLInputElement> & { label: string; helper?: string }) {
  return (
    <label className="vn-field">
      <span>{label}</span>
      <input className="vn-input" type="number" min="0" step="0.01" inputMode="decimal" {...props} />
      {helper && <small>{helper}</small>}
    </label>
  );
}
