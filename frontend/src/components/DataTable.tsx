import { useEffect, useMemo, useState, type ReactNode } from 'react';
import { Pagination } from '../styles/design-system/Pagination';
import { compareSortValues, sortIndicator, toggleSortColumn, type SortOrder } from '../utils/tableSort';
import './DataTable.scss';

export type Column<T> = {
  key: string;
  label: ReactNode;
  align?: 'left' | 'right';
  sortable?: boolean;
  /** Value used for client-side sorting and as the default sort target. */
  sortValue?: (row: T) => string | number | null | undefined;
  defaultOrder?: SortOrder;
  render: (row: T) => ReactNode;
  className?: string;
  cellClassName?: (row: T) => string | undefined;
};

type Props<T> = {
  columns: Column<T>[];
  rows: T[];
  rowKey: (row: T, index: number) => string;
  loading?: boolean;
  loadingLabel?: ReactNode;
  empty?: ReactNode;
  /**
   * Sorting is uncontrolled by default (the table sorts `rows` itself). Pass `sortCol` and
   * `onSortChange` to control it instead — use that when the sort runs on the server and `rows`
   * arrive pre-sorted.
   */
  sortCol?: string;
  sortOrder?: SortOrder;
  onSortChange?: (col: string, order: SortOrder) => void;
  defaultSortCol?: string;
  defaultSortOrder?: SortOrder;
  selectable?: boolean;
  selected?: Set<string>;
  onToggleRow?: (key: string, checked: boolean) => void;
  onToggleAll?: (checked: boolean) => void;
  onRowClick?: (row: T) => void;
  rowClassName?: (row: T) => string | undefined;
  wrapperClassName?: string;
  className?: string;
  /**
   * Rows per page. Omitted means "show everything" — a 47-row factor list needs no pager, a
   * 200-row screening result does. Sorting and selection stay over the *visible* page, which is what
   * a reader means by "select all".
   */
  pageSize?: number;
  pageSizeOptions?: readonly number[];
};

export function DataTable<T>({
  columns,
  rows,
  rowKey,
  loading,
  loadingLabel,
  empty,
  sortCol,
  sortOrder = 'asc',
  onSortChange,
  defaultSortCol,
  defaultSortOrder = 'asc',
  selectable,
  selected,
  onToggleRow,
  onToggleAll,
  onRowClick,
  rowClassName,
  wrapperClassName,
  className,
  pageSize,
  pageSizeOptions,
}: Props<T>) {
  const controlled = Boolean(onSortChange);
  const [internalSort, setInternalSort] = useState<{ col: string; order: SortOrder }>({
    col: defaultSortCol ?? '',
    order: defaultSortOrder,
  });
  const active = controlled ? { col: sortCol ?? '', order: sortOrder } : internalSort;

  const sortedRows = useMemo(() => {
    if (controlled || !active.col) return rows;
    const column = columns.find((c) => c.key === active.col);
    if (!column?.sortValue) return rows;
    return [...rows].sort((a, b) =>
      compareSortValues(column.sortValue!(a), column.sortValue!(b), active.order),
    );
  }, [rows, columns, active.col, active.order, controlled]);

  const [page, setPage] = useState(0);
  const [size, setSize] = useState(pageSize ?? 0);

  useEffect(() => {
    setSize(pageSize ?? 0);
  }, [pageSize]);

  const pagedRows = useMemo(() => {
    if (!size) return sortedRows;
    const start = page * size;
    // A page that no longer exists (rows filtered away) falls back to the last real one.
    if (start >= sortedRows.length) return sortedRows.slice(0, size);
    return sortedRows.slice(start, start + size);
  }, [sortedRows, size, page]);

  function onSortClick(column: Column<T>) {
    const next = toggleSortColumn(active.col, active.order, column.key, column.defaultOrder === 'desc');
    if (controlled) onSortChange?.(next.col, next.order);
    else setInternalSort(next);
  }

  if (loading) {
    return <p className="table-empty">{loadingLabel ?? '…'}</p>;
  }
  if (sortedRows.length === 0) {
    return <div className="table-empty">{empty}</div>;
  }

  const allSelected =
    selectable && selected ? pagedRows.every((row, index) => selected.has(rowKey(row, index))) : false;

  return (
    <div className={wrapperClassName ? `data-table-wrap ${wrapperClassName}` : 'data-table-wrap'}>
      <table className={className ? `data-table ${className}` : 'data-table'}>
        <thead>
          <tr>
            {selectable && (
              <th className="data-table-select">
                <input
                  type="checkbox"
                  checked={allSelected}
                  onChange={(e) => onToggleAll?.(e.target.checked)}
                  aria-label="select all"
                />
              </th>
            )}
            {columns.map((column) => (
              <th
                key={column.key}
                className={[
                  column.align === 'right' ? 'num' : '',
                  column.sortable ? 'sortable' : '',
                  column.className ?? '',
                ]
                  .filter(Boolean)
                  .join(' ') || undefined}
                onClick={column.sortable ? () => onSortClick(column) : undefined}
              >
                {column.label}
                {column.sortable ? sortIndicator(active.col, column.key, active.order) : ''}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {pagedRows.map((row, index) => {
            const key = rowKey(row, index);
            return (
              <tr
                key={key}
                className={
                  [rowClassName?.(row) ?? '', onRowClick ? 'clickable' : ''].filter(Boolean).join(' ') ||
                  undefined
                }
                onClick={onRowClick ? () => onRowClick(row) : undefined}
              >
                {selectable && (
                  <td className="data-table-select" onClick={(e) => e.stopPropagation()}>
                    <input
                      type="checkbox"
                      checked={selected?.has(key) ?? false}
                      onChange={(e) => onToggleRow?.(key, e.target.checked)}
                      aria-label={`select ${key}`}
                    />
                  </td>
                )}
                {columns.map((column) => (
                  <td
                    key={column.key}
                    className={
                      [column.align === 'right' ? 'num' : '', column.cellClassName?.(row) ?? '']
                        .filter(Boolean)
                        .join(' ') || undefined
                    }
                  >
                    {column.render(row)}
                  </td>
                ))}
              </tr>
            );
          })}
        </tbody>
      </table>
      {size > 0 && (
        <Pagination
          total={sortedRows.length}
          page={page}
          pageSize={size}
          pageSizeOptions={pageSizeOptions}
          onPageChange={setPage}
          onPageSizeChange={(next) => {
            setSize(next);
            setPage(0);
          }}
        />
      )}
    </div>
  );
}
