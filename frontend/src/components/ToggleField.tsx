import type { InputHTMLAttributes } from 'react';

export function ToggleField({ label, helper, ...props }: InputHTMLAttributes<HTMLInputElement> & { label: string; helper?: string }) {
  return (
    <label className="vn-toggle-field">
      <input type="checkbox" {...props} />
      <span><strong>{label}</strong>{helper && <small>{helper}</small>}</span>
    </label>
  );
}
