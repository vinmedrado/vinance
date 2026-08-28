import { EmptyState } from './EmptyState';

type MarketTableProps<T extends Record<string, unknown>> = {
  items: T[];
  columns: { key: string; label: string; render?: (item: T) => string }[];
  emptyTitle?: string;
  emptyDescription?: string;
};

function displayValue(value: unknown) {
  if (value === null || value === undefined || value === '') return '—';
  if (typeof value === 'boolean') return value ? 'sim' : 'não';
  return String(value);
}

export function MarketTable<T extends Record<string, unknown>>({ items, columns, emptyTitle = 'Sem dados', emptyDescription = 'O backend não retornou registros para esta visão.' }: MarketTableProps<T>) {
  if (items.length === 0) return <EmptyState title={emptyTitle} description={emptyDescription} />;
  return (
    <div className="vn-table-wrap">
      <table className="vn-market-table">
        <thead><tr>{columns.map((column) => <th key={column.key}>{column.label}</th>)}</tr></thead>
        <tbody>
          {items.map((item, index) => (
            <tr key={index}>
              {columns.map((column) => <td key={column.key}>{column.render ? column.render(item) : displayValue(item[column.key])}</td>)}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
