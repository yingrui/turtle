import { useTranslation } from 'react-i18next';

export const DEFAULT_PAGE_SIZE_OPTIONS = [10, 25, 50, 100] as const;

export type PaginationProps = {
  total: number;
  page: number;
  pageSize: number;
  loading?: boolean;
  pageSizeOptions?: readonly number[];
  onPageChange: (page: number) => void;
  onPageSizeChange: (size: number) => void;
  className?: string;
  /** When true, bar uses compact padding (e.g. sidebar lists). */
  compact?: boolean;
};

export function Pagination({
  total,
  page,
  pageSize,
  loading = false,
  pageSizeOptions = DEFAULT_PAGE_SIZE_OPTIONS,
  onPageChange,
  onPageSizeChange,
  className = '',
  compact = false,
}: PaginationProps) {
  const { t } = useTranslation('common');
  const totalPages = total > 0 ? Math.ceil(total / pageSize) : 0;
  const from = total > 0 ? page * pageSize + 1 : 0;
  const to = total > 0 ? Math.min((page + 1) * pageSize, total) : 0;

  if (total === 0) {
    return null;
  }

  const safePageSize = (pageSizeOptions as readonly number[]).includes(pageSize)
    ? pageSize
    : pageSizeOptions[0];

  return (
    <nav
      className={['ds-pagination', compact ? 'ds-pagination--compact' : '', className]
        .filter(Boolean)
        .join(' ')}
      aria-label={t('pagination.aria')}
    >
      <div className="ds-pagination__info">
        <span className="ds-pagination__range">
          {t('pagination.range', { from, to, total })}
        </span>
        <label className="ds-pagination__size">
          <span>{t('pagination.perPage')}</span>
          <select
            value={safePageSize}
            onChange={(e) => onPageSizeChange(Number(e.target.value))}
            disabled={loading}
            aria-label={t('pagination.perPage')}
          >
            {pageSizeOptions.map((n) => (
              <option key={n} value={n}>
                {n}
              </option>
            ))}
          </select>
        </label>
      </div>
      {totalPages > 1 && (
        <div className="ds-pagination__nav">
          <button
            type="button"
            className="btn btn-secondary btn-sm"
            disabled={page <= 0 || loading}
            onClick={() => onPageChange(Math.max(0, page - 1))}
          >
            {t('pagination.previous')}
          </button>
          <span className="ds-pagination__status">
            {t('pagination.pageStatus', { current: page + 1, total: totalPages })}
          </span>
          <button
            type="button"
            className="btn btn-secondary btn-sm"
            disabled={page >= totalPages - 1 || loading}
            onClick={() => onPageChange(Math.min(totalPages - 1, page + 1))}
          >
            {t('pagination.next')}
          </button>
        </div>
      )}
    </nav>
  );
}
