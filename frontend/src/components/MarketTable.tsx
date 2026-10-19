import type { ReactNode } from 'react';
import { EmptyState } from './EmptyState';

export type MarketColumn<T extends Record<string, unknown>> = {
  key: string;
  label: string;
  render?: (item: T) => ReactNode;
};

type MarketTableProps<T extends Record<string, unknown>> = {
  items: T[];
  columns: MarketColumn<T>[];
  emptyTitle?: string;
  emptyDescription?: string;
  ariaLabel?: string;
  primaryKey?: string;
  secondaryKey?: string;
  getRowKey?: (item: T, index: number) => string | number;
};

function displayValue(value: unknown): ReactNode {
  if (value === null || value === undefined || value === '') return '—';
  if (typeof value === 'boolean') return value ? 'sim' : 'não';
  return String(value);
}

function renderedValue<T extends Record<string, unknown>>(item: T, column: MarketColumn<T>) {
  return column.render ? column.render(item) : displayValue(item[column.key]);
}

export function MarketTable<T extends Record<string, unknown>>({
  items,
  columns,
  emptyTitle = 'Sem dados',
  emptyDescription = 'Nenhum registro está disponível para esta visão.',
  ariaLabel = 'Dados de mercado',
  primaryKey,
  secondaryKey,
  getRowKey,
}: MarketTableProps<T>) {
  if (items.length === 0) return <EmptyState title={emptyTitle} description={emptyDescription} />;
  const primary = columns.find((column) => column.key === primaryKey) ?? columns[0];
  const secondary = columns.find((column) => column.key === secondaryKey)
    ?? columns.find((column) => column.key !== primary.key)
    ?? primary;
  const detailColumns = columns.filter((column) => column.key !== primary.key && column.key !== secondary.key);
  const rowKey = (item: T, index: number) => getRowKey?.(item, index)
    ?? String(item.id ?? item.ticker ?? item.symbol ?? item.code ?? index);

  return (
    <>
      <div className="vn-table-wrap vn-market-table-wrap">
        <table className="vn-market-table" aria-label={ariaLabel}>
          <thead><tr>{columns.map((column) => <th key={column.key} scope="col">{column.label}</th>)}</tr></thead>
          <tbody>
            {items.map((item, index) => (
              <tr key={rowKey(item, index)}>
                {columns.map((column) => <td key={column.key}>{renderedValue(item, column)}</td>)}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="vn-market-mobile-list" aria-label={`${ariaLabel} em formato compacto`}>
        {items.map((item, index) => (
          <article className="vn-market-mobile-item" key={rowKey(item, index)}>
            <div className="vn-market-mobile-item__headline">
              <strong>{renderedValue(item, primary)}</strong>
              <span>{renderedValue(item, secondary)}</span>
            </div>
            {detailColumns.length > 0 && <dl>
              {detailColumns.map((column) => <div key={column.key}>
                <dt>{column.label}</dt>
                <dd>{renderedValue(item, column)}</dd>
              </div>)}
            </dl>}
          </article>
        ))}
      </div>
    </>
  );
}
