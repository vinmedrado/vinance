export function Toast({ message, tone = 'success' }: { message: string; tone?: 'success' | 'warning' | 'danger' }) {
  return <div className={`vn-toast vn-toast--${tone}`} role="status" aria-live="polite">{message}</div>;
}
