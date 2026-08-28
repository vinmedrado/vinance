import type { SelectHTMLAttributes } from 'react';

export type SelectOption = { value: string; label: string };

export function SelectField({ label, helper, options, ...props }: SelectHTMLAttributes<HTMLSelectElement> & { label: string; helper?: string; options: SelectOption[] }) {
  return (
    <label className="vn-field">
      <span>{label}</span>
      <select className="vn-input" {...props}>
        {options.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
      </select>
      {helper && <small>{helper}</small>}
    </label>
  );
}
