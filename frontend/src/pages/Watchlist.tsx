import { useCallback, useEffect, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { toast } from 'sonner';
import { apiFetch } from '../utils/api';
import { DataTable, type Column } from '../components/DataTable';
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


  const columns: Column<WatchlistItem>[] = [
    {
      key: 'ts_code',
      label: t('quote.col.ts_code'),
      sortable: true,
      sortValue: (row) => row.ts_code,
      render: (row) => <Link to={`/stocks/${encodeURIComponent(row.ts_code)}`}>{row.ts_code}</Link>,
    },
    {
      key: 'name',
      label: t('quote.col.name'),
      sortable: true,
      sortValue: (row) => row.name,
      render: (row) => row.name ?? '—',
    },
    {
      key: 'close',
      label: t('quote.col.close'),
      align: 'right',
      sortable: true,
      defaultOrder: 'desc',
      sortValue: (row) => row.quote?.close,
      render: (row) => (row.quote?.close != null ? row.quote.close.toFixed(2) : '—'),
    },
    {
      key: 'pct_chg',
      label: t('quote.col.pct_chg'),
      align: 'right',
      sortable: true,
      defaultOrder: 'desc',
      sortValue: (row) => row.quote?.pct_chg,
      cellClassName: (row) => {
        const pct = row.quote?.pct_chg;
        if (pct == null) return undefined;
        return pct > 0 ? 'price-up' : pct < 0 ? 'price-down' : 'price-flat';
      },
      render: (row) => {
        const pct = row.quote?.pct_chg;
        return pct != null ? `${pct > 0 ? '+' : ''}${pct.toFixed(2)}%` : '—';
      },
    },
    {
      key: 'industry',
      label: t('quote.col.industry'),
      sortable: true,
      sortValue: (row) => row.industry,
      render: (row) => row.industry ?? '—',
    },
    {
      key: 'actions',
      label: t('quote.col.actions'),
      render: (row) => (
        <button type="button" className="btn btn-sm btn-secondary" onClick={() => remove(row.ts_code)}>
          {t('watchlist.remove')}
        </button>
      ),
    },
  ];

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

          <DataTable
            columns={columns}
            rows={items}
            rowKey={(row) => row.ts_code}
            loading={loadingStocks}
            loadingLabel={t('watchlist.loading')}
            defaultSortCol="pct_chg"
            defaultSortOrder="desc"
            empty={
              <div className="watchlist-empty-stocks">
                <p className="watchlist-muted">{t('watchlist.emptyStocks')}</p>
                <Link to="/screening" className="btn btn-primary btn-sm">
                  {t('watchlist.goPick')}
                </Link>
              </div>
            }
          />
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
