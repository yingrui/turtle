import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { toast } from 'sonner';
import { apiFetch } from '../utils/api';
import { compareSortValues, sortIndicator, toggleSortColumn, type SortOrder } from '../utils/tableSort';
import './Watchlist.scss';

type Quote = {
  trade_date: string;
  close: number;
  pct_chg: number;
};

type WatchlistItem = {
  ts_code: string;
  name?: string;
  industry?: string;
  quote: Quote | null;
};

export function Watchlist() {
  const { t } = useTranslation();
  const [searchParams, setSearchParams] = useSearchParams();

  const [portfolios, setPortfolios] = useState<string[]>([]);
  const [portfolio, setPortfolio] = useState('');
  const [items, setItems] = useState<WatchlistItem[]>([]);
  const [asOfDate, setAsOfDate] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadingStocks, setLoadingStocks] = useState(false);

  const [createOpen, setCreateOpen] = useState(false);
  const [newName, setNewName] = useState('');
  const [creating, setCreating] = useState(false);

  const [sortCol, setSortCol] = useState('pct_chg');
  const [sortOrder, setSortOrder] = useState<SortOrder>('desc');

  const sortedItems = useMemo(() => {
    const rows = [...items];
    rows.sort((a, b) => {
      let av: string | number | null | undefined;
      let bv: string | number | null | undefined;
      if (sortCol === 'ts_code') {
        av = a.ts_code;
        bv = b.ts_code;
      } else if (sortCol === 'name') {
        av = a.name;
        bv = b.name;
      } else if (sortCol === 'industry') {
        av = a.industry;
        bv = b.industry;
      } else if (sortCol === 'close') {
        av = a.quote?.close;
        bv = b.quote?.close;
      } else {
        av = a.quote?.pct_chg;
        bv = b.quote?.pct_chg;
      }
      return compareSortValues(av, bv, sortOrder);
    });
    return rows;
  }, [items, sortCol, sortOrder]);

  function onSortColumn(col: string, defaultDesc = false) {
    const next = toggleSortColumn(sortCol, sortOrder, col, defaultDesc);
    setSortCol(next.col);
    setSortOrder(next.order);
  }

  function thSort(col: string, label: string, defaultDesc = false) {
    return (
      <th className="sortable" onClick={() => onSortColumn(col, defaultDesc)}>
        {label}
        {sortIndicator(sortCol, col, sortOrder)}
      </th>
    );
  }

  const selectPortfolio = useCallback(
    (name: string) => {
      setPortfolio(name);
      if (name) {
        setSearchParams({ portfolio: name }, { replace: true });
      } else {
        setSearchParams({}, { replace: true });
      }
    },
    [setSearchParams],
  );

  const refreshPortfolios = useCallback(
    async (prefer?: string) => {
      const d = await apiFetch<{ portfolios: string[] }>('/api/portfolios');
      setPortfolios(d.portfolios);
      if (d.portfolios.length === 0) {
        selectPortfolio('');
        return d.portfolios;
      }
      const candidate = prefer ?? searchParams.get('portfolio') ?? '';
      const next = d.portfolios.includes(candidate) ? candidate : d.portfolios[0];
      selectPortfolio(next);
      return d.portfolios;
    },
    [searchParams, selectPortfolio],
  );

  const loadStocks = useCallback(
    async (name: string) => {
      if (!name) {
        setItems([]);
        setAsOfDate(null);
        return;
      }
      setLoadingStocks(true);
      try {
        const data = await apiFetch<{
          portfolio: string;
          as_of_date: string | null;
          items: WatchlistItem[];
        }>(`/api/portfolios/${encodeURIComponent(name)}/watchlist`);
        setItems(data.items);
        setAsOfDate(data.as_of_date);
      } catch {
        toast.error(t('watchlist.loadError'));
        setItems([]);
        setAsOfDate(null);
      } finally {
        setLoadingStocks(false);
      }
    },
    [t],
  );

  useEffect(() => {
    refreshPortfolios()
      .catch(() => toast.error(t('watchlist.loadPortfoliosError')))
      .finally(() => setLoading(false));
    // Initial load only
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (portfolio) {
      loadStocks(portfolio);
    }
  }, [portfolio, loadStocks]);

  async function onCreate(e: React.FormEvent) {
    e.preventDefault();
    const trimmed = newName.trim();
    if (!trimmed) {
      toast.error(t('portfolio.nameRequired'));
      return;
    }
    setCreating(true);
    try {
      await apiFetch('/api/portfolios', {
        method: 'POST',
        body: JSON.stringify({ name: trimmed }),
      });
      toast.success(t('portfolio.created', { name: trimmed }));
      setNewName('');
      setCreateOpen(false);
      await refreshPortfolios(trimmed);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : t('portfolio.createFailed'));
    } finally {
      setCreating(false);
    }
  }

  async function onDeletePortfolio() {
    if (!portfolio || !window.confirm(t('portfolio.deleteConfirm', { name: portfolio }))) return;
    try {
      await apiFetch(`/api/portfolios/${encodeURIComponent(portfolio)}`, { method: 'DELETE' });
      toast.success(t('portfolio.deleted', { name: portfolio }));
      await refreshPortfolios();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : t('portfolio.deleteFailed'));
    }
  }

  async function remove(tsCode: string) {
    if (!portfolio) return;
    try {
      await apiFetch(
        `/api/portfolios/${encodeURIComponent(portfolio)}/watchlist/${encodeURIComponent(tsCode)}`,
        { method: 'DELETE' },
      );
      toast.success(t('watchlist.removed', { code: tsCode, portfolio }));
      loadStocks(portfolio);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed');
    }
  }

  const hasPortfolios = portfolios.length > 0;

  return (
    <div className="page-card watchlist-page">
      <h1 className="page-title">{t('nav.watchlist')}</h1>
      <p className="watchlist-intro">{t('watchlist.subtitle')}</p>

      {loading ? (
        <p className="watchlist-muted">{t('watchlist.loading')}</p>
      ) : !hasPortfolios ? (
        <section className="watchlist-empty-panel">
          <h2>{t('watchlist.noPortfolioTitle')}</h2>
          <p className="watchlist-muted">{t('watchlist.noPortfolioDesc')}</p>
          <form className="watchlist-create-form" onSubmit={onCreate}>
            <div className="form-row">
              <label htmlFor="watchlist-new-name">{t('portfolio.newName')}</label>
              <input
                id="watchlist-new-name"
                type="text"
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                placeholder={t('portfolio.namePlaceholder')}
                autoComplete="off"
              />
            </div>
            <button type="submit" className="btn btn-primary" disabled={creating || !newName.trim()}>
              {creating ? t('portfolio.creating') : t('watchlist.createPortfolio')}
            </button>
          </form>
        </section>
      ) : (
        <>
          <div className="watchlist-toolbar">
            <div className="form-row watchlist-select">
              <label htmlFor="watchlist-portfolio">{t('watchlist.portfolio')}</label>
              <select
                id="watchlist-portfolio"
                value={portfolio}
                onChange={(e) => selectPortfolio(e.target.value)}
              >
                {portfolios.map((p) => (
                  <option key={p} value={p}>{p}</option>
                ))}
              </select>
            </div>
            <div className="watchlist-toolbar-actions">
              <button type="button" className="btn btn-primary btn-sm" onClick={() => setCreateOpen(true)}>
                {t('watchlist.createPortfolio')}
              </button>
              <Link
                to={`/portfolio?portfolio=${encodeURIComponent(portfolio)}`}
                className="btn btn-secondary btn-sm"
              >
                {t('watchlist.configLink')}
              </Link>
              <button type="button" className="btn btn-secondary btn-sm" onClick={onDeletePortfolio}>
                {t('watchlist.deletePortfolio')}
              </button>
            </div>
          </div>

          {asOfDate && (
            <p className="watchlist-muted watchlist-asof">
              {t('data.status.asOf')}: {asOfDate}
            </p>
          )}

          {loadingStocks ? (
            <p className="watchlist-muted">{t('watchlist.loading')}</p>
          ) : items.length === 0 ? (
            <div className="watchlist-empty-stocks">
              <p className="watchlist-muted">{t('watchlist.emptyStocks')}</p>
              <Link to="/screening" className="btn btn-primary btn-sm">
                {t('watchlist.goPick')}
              </Link>
            </div>
          ) : (
            <table className="data-table">
              <thead>
                <tr>
                  {thSort('ts_code', t('quote.col.ts_code'))}
                  {thSort('name', t('quote.col.name'))}
                  {thSort('close', t('quote.col.close'), true)}
                  {thSort('pct_chg', t('quote.col.pct_chg'), true)}
                  {thSort('industry', t('quote.col.industry'))}
                  <th>{t('quote.col.actions')}</th>
                </tr>
              </thead>
              <tbody>
                {sortedItems.map((item) => {
                  const pct = item.quote?.pct_chg;
                  const pctClass = pct != null ? (pct > 0 ? 'up' : pct < 0 ? 'down' : '') : '';
                  return (
                    <tr key={item.ts_code}>
                      <td>
                        <Link to={`/stocks/${encodeURIComponent(item.ts_code)}`}>{item.ts_code}</Link>
                      </td>
                      <td>{item.name ?? '—'}</td>
                      <td>{item.quote?.close != null ? item.quote.close.toFixed(2) : '—'}</td>
                      <td className={pctClass}>
                        {pct != null ? `${pct > 0 ? '+' : ''}${pct.toFixed(2)}%` : '—'}
                      </td>
                      <td>{item.industry ?? '—'}</td>
                      <td>
                        <button
                          type="button"
                          className="btn btn-sm btn-secondary"
                          onClick={() => remove(item.ts_code)}
                        >
                          {t('watchlist.remove')}
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </>
      )}

      {createOpen && (
        <div className="watchlist-modal-backdrop" onClick={() => setCreateOpen(false)}>
          <div className="watchlist-modal" onClick={(e) => e.stopPropagation()}>
            <h2>{t('watchlist.createPortfolio')}</h2>
            <p className="watchlist-muted">{t('portfolio.createDesc')}</p>
            <form onSubmit={onCreate}>
              <div className="form-row">
                <label htmlFor="watchlist-modal-name">{t('portfolio.newName')}</label>
                <input
                  id="watchlist-modal-name"
                  type="text"
                  value={newName}
                  onChange={(e) => setNewName(e.target.value)}
                  placeholder={t('portfolio.namePlaceholder')}
                  autoFocus
                />
              </div>
              <div className="watchlist-modal-actions">
                <button type="submit" className="btn btn-primary" disabled={creating || !newName.trim()}>
                  {creating ? t('portfolio.creating') : t('portfolio.create')}
                </button>
                <button type="button" className="btn btn-secondary" onClick={() => setCreateOpen(false)}>
                  {t('screening.cancel')}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
