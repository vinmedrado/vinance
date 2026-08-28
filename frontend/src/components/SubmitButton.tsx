import type { ButtonHTMLAttributes, PropsWithChildren } from 'react';
import { Button } from './Button';

export function SubmitButton({ loading, children, loadingLabel = 'Salvando...', ...props }: PropsWithChildren<ButtonHTMLAttributes<HTMLButtonElement> & { loading?: boolean; loadingLabel?: string }>) {
  return <Button type="submit" disabled={loading || props.disabled} {...props}>{loading ? loadingLabel : children}</Button>;
}
