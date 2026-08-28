import type { ButtonHTMLAttributes, PropsWithChildren } from 'react';

type ButtonProps = PropsWithChildren<ButtonHTMLAttributes<HTMLButtonElement> & { variant?: 'primary' | 'secondary' | 'ghost' }>;

export function Button({ variant = 'primary', className = '', children, ...props }: ButtonProps) {
  return <button className={`vn-button vn-button--${variant} ${className}`.trim()} {...props}>{children}</button>;
}
