import { expect, test } from 'vitest';

import { localDateInputValue } from '../../src/utils/localDate';

test('mantém a data civil de São Paulo depois das 21h sem convertê-la para UTC', () => {
  expect(
    localDateInputValue(
      new Date('2026-10-06T02:30:00.000Z'),
      'America/Sao_Paulo',
    ),
  ).toBe('2026-10-05');
});

test('formata a data local usando o calendário da máquina quando não há timezone explícito', () => {
  const date = new Date(2026, 9, 6, 23, 30, 0);
  expect(localDateInputValue(date)).toBe('2026-10-06');
});
