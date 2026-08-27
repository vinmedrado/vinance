import { useState } from 'react';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';
import { Modal } from '../../src/components/Modal';

function Harness() {
  const [open, setOpen] = useState(false);
  return (
    <>
      <button type="button" onClick={() => setOpen(true)}>Abrir preferências</button>
      <Modal open={open} title="Preferências de alerta" onClose={() => setOpen(false)}>
        <button type="button">Salvar</button>
      </Modal>
    </>
  );
}

describe('Modal acessível', () => {
  it('nomeia o diálogo, prende o foco, fecha com Escape e restaura o foco', async () => {
    const user = userEvent.setup();
    render(<Harness />);
    const opener = screen.getByRole('button', { name: 'Abrir preferências' });

    await user.click(opener);
    expect(screen.getByRole('dialog', { name: 'Preferências de alerta' })).toBeVisible();
    const close = screen.getByRole('button', { name: 'Fechar Preferências de alerta' });
    const save = screen.getByRole('button', { name: 'Salvar' });
    expect(close).toHaveFocus();

    save.focus();
    await user.tab();
    expect(close).toHaveFocus();
    await user.tab({ shift: true });
    expect(save).toHaveFocus();

    await user.keyboard('{Escape}');
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    expect(opener).toHaveFocus();
  });
});
