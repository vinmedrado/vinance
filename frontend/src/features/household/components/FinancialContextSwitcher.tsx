import { useEffect, useRef, useState, type KeyboardEvent as ReactKeyboardEvent } from 'react';
import { ChevronDown, LockKeyhole, UsersRound } from 'lucide-react';
import { useFinancialContext, financialContextCopy } from '../context/FinancialContextProvider';

export function FinancialContextSwitcher({ compact = false }: { compact?: boolean }) {
  const context = useFinancialContext();
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    function close(event: PointerEvent) {
      if (!rootRef.current?.contains(event.target as Node)) setOpen(false);
    }
    function keyboard(event: KeyboardEvent) {
      if (event.key === 'Escape') {
        setOpen(false);
        triggerRef.current?.focus();
      }
    }
    document.addEventListener('pointerdown', close);
    document.addEventListener('keydown', keyboard);
    const focusTimer = window.setTimeout(() => {
      const active = menuRef.current?.querySelector<HTMLElement>('[aria-checked="true"]');
      const first = menuRef.current?.querySelector<HTMLElement>('[role="menuitemradio"]');
      (active ?? first)?.focus();
    }, 0);
    return () => {
      window.clearTimeout(focusTimer);
      document.removeEventListener('pointerdown', close);
      document.removeEventListener('keydown', keyboard);
    };
  }, [open]);

  const Icon = context.activeHousehold?.household_type === 'SHARED' ? UsersRound : LockKeyhole;
  const activeHouseholdName = context.activeHousehold?.household_type === 'SHARED'
    ? context.activeHousehold.name
    : null;

  function navigateMenu(event: ReactKeyboardEvent<HTMLDivElement>) {
    if (event.key === 'Tab') {
      setOpen(false);
      return;
    }
    if (!['ArrowDown', 'ArrowUp', 'Home', 'End'].includes(event.key)) return;
    const items = Array.from(
      menuRef.current?.querySelectorAll<HTMLButtonElement>('[role="menuitemradio"]') ?? [],
    );
    if (items.length === 0) return;
    event.preventDefault();
    const current = Math.max(0, items.indexOf(document.activeElement as HTMLButtonElement));
    const next = event.key === 'Home'
      ? 0
      : event.key === 'End'
        ? items.length - 1
        : event.key === 'ArrowDown'
          ? (current + 1) % items.length
          : (current - 1 + items.length) % items.length;
    items[next].focus();
  }

  return (
    <div ref={rootRef} className={`vn-financial-context-switcher${compact ? ' is-compact' : ''}`}>
      <button
        ref={triggerRef}
        type="button"
        className="vn-financial-context-switcher__trigger"
        aria-haspopup="menu"
        aria-expanded={open}
        aria-label={`Contexto financeiro: ${context.label}${activeHouseholdName ? ` — ${activeHouseholdName}` : ''}. Abrir seletor`}
        onClick={() => setOpen((value) => !value)}
        disabled={context.isLoading || context.isSwitching}
      >
        <Icon size={17} aria-hidden="true" />
        <span>
          <strong>{context.isLoading ? 'Carregando contexto…' : context.label}</strong>
          {(activeHouseholdName || !compact) && (
            <small>{activeHouseholdName ?? 'Somente você'}</small>
          )}
        </span>
        <ChevronDown size={15} aria-hidden="true" />
      </button>
      {open && (
        <div
          ref={menuRef}
          className="vn-financial-context-switcher__menu"
          role="menu"
          aria-label="Escolher contexto financeiro"
          onKeyDown={navigateMenu}
        >
          <header role="presentation">
            <strong>Onde você está trabalhando?</strong>
            <p>A troca altera os dados e as análises exibidos.</p>
          </header>
          {context.households.map((household) => {
            const copy = financialContextCopy(household);
            const ItemIcon = household.household_type === 'SHARED' ? UsersRound : LockKeyhole;
            const active = household.id === context.activeHousehold?.id;
            return (
              <button
                key={household.id}
                type="button"
                role="menuitemradio"
                aria-checked={active}
                tabIndex={active ? 0 : -1}
                className={active ? 'is-active' : undefined}
                onClick={() => {
                  setOpen(false);
                  void context.switchContext(household.id).catch(() => undefined);
                }}
              >
                <ItemIcon size={18} aria-hidden="true" />
                <span>
                  <strong>{copy.label}</strong>
                  <small>{household.household_type === 'SHARED' ? household.name : copy.description}</small>
                </span>
                <i aria-hidden="true" />
              </button>
            );
          })}
        </div>
      )}
      {Boolean(context.error) && (
        <p className="vn-financial-context-switcher__error" role="alert">
          Não foi possível atualizar o contexto financeiro. Tente novamente.
        </p>
      )}
    </div>
  );
}
