import { useId, type InputHTMLAttributes } from 'react';

export function MoneyInput({ label, helper, 'aria-label': ariaLabel, 'aria-describedby': describedBy, ...props }: InputHTMLAttributes<HTMLInputElement> & { label: string; helper?: string }) {
  const helperId = useId();
  const descriptions = [describedBy, helper ? helperId : null].filter(Boolean).join(' ') || undefined;

  return (
    <label className="vn-field">
      <span>{label}</span>
      <input
        className="vn-input"
        type="number"
        min="0"
        step="0.01"
        inputMode="decimal"
        aria-label={ariaLabel ?? label}
        aria-describedby={descriptions}
        {...props}
      />
      {helper && <small id={helperId}>{helper}</small>}
    </label>
  );
}
