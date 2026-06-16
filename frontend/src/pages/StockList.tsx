import { useCallback, useEffect, useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { toast } from 'sonner';
import { apiFetch } from '../utils/api';
import { Pagination } from '../styles/design-system/Pagination';
import './StockList.scss';

type Quote = {
  trade_date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  pct_chg: number;
  vol: number;
  amount: number;
};

type StockItem = {
  ts_code: string;
  symbol: string;
  name: string;
  industry: string;
  market: string;
  exchange: string;
  list_status: string;
  quote: Quote | null;
};

type UniverseMeta = {
  latest_trade_date: string | null;
  listed_count: number;
  exchanges: Record<string, number>;
  markets: string[];
  industries: string[];
};

type IndustrySummaryItem = {
  industry: string;
  stock_count: number;
  avg_pct_chg: number;
  up_count: number;
  down_count: number;
};

type Chip = { id: string; exchange?: string; market?: string };

const CHIPS: Chip[] = [
  { id: 'all' },
  { id: 'SH', exchange: 'SH' },
  { id: 'SZ', exchange: 'SZ' },
  { id: 'CYB', market: '创业板' },
  { id: 'KCB', market: '科创板' },
  { id: 'BJ', exchange: 'BJ' },
];

const SORTABLE = [
  'ts_code',
  'name',
  'close',
  'pct_chg',
  'open',
  'high',
  'low',
  'vol',
  'amount',
  'industry',
] as const;

const DISPLAY_COLS = [
  'ts_code',
  'name',
  'close',
  'pct_chg',
  'open',
  'high',
  'low',
  'vol',
  'amount',
  'industry',
] as const;

function chipFromParams(sp: URLSearchParams): Chip {
  const chipId = sp.get('chip') ?? 'all';
  return CHIPS.find((c) => c.id === chipId) ?? CHIPS[0];
}

function formatVol(v: number | undefined) {
  if (v == null) return '—';
  if (v >= 10000) return `${(v / 10000).toFixed(1)}万`;
  return v.toFixed(0);
}

function formatAmount(v: number | undefined) {
  if (v == null) return '—';
  if (v >= 100000) return `${(v / 100000).toFixed(2)}亿`;
  if (v >= 10) return `${(v / 10).toFixed(1)}万`;
  return v.toFixed(0);
}

function formatPct(v: number | undefined) {
  if (v == null) return '—';
  const sign = v > 0 ? '+' : '';
  return `${sign}${v.toFixed(2)}%`;
}

function formatPrice(v: number | undefined) {
  if (v == null) return '—';
  return v.toFixed(2);
}

function exportCsv(items: StockItem[], filename: string) {
  const headers = ['ts_code', 'name', 'close', 'pct_chg', 'open', 'high', 'low', 'vol', 'amount', 'industry'];
  const rows = items.map((row) =>
    [
      row.ts_code,
      row.name,
      row.quote?.close ?? '',
      row.quote?.pct_chg ?? '',
      row.quote?.open ?? '',
      row.quote?.high ?? '',
      row.quote?.low ?? '',
      row.quote?.vol ?? '',
      row.quote?.amount ?? '',
      row.industry ?? '',
    ].join(','),
  );
  const blob = new Blob([`\uFEFF${[headers.join(','), ...rows].join('\n')}`], { type: 'text/csv;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

export function StockList() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();

  const initialChip = chipFromParams(searchParams);

  const [meta, setMeta] = useState<UniverseMeta | null>(null);
  const [industrySummary, setIndustrySummary] = useState<IndustrySummaryItem[]>([]);
  const [items, setItems] = useState<StockItem[]>([]);
  const [total, setTotal] = useState(0);
  const [asOfDate, setAsOfDate] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const [q, setQ] = useState(searchParams.get('q') ?? '');
  const [debouncedQ, setDebouncedQ] = useState(searchParams.get('q')?.trim() ?? '');
  const [industry, setIndustry] = useState(searchParams.get('industry') ?? '');
  const [listStatus, setListStatus] = useState(searchParams.get('list_status') ?? 'L');
  const [excludeSt, setExcludeSt] = useState(searchParams.get('exclude_st') !== 'false');
  const [activeChip, setActiveChip] = useState(initialChip.id);
  const [exchange, setExchange] = useState<string | undefined>(initialChip.exchange);
  const [market, setMarket] = useState<string | undefined>(initialChip.market);

  const [page, setPage] = useState(Number(searchParams.get('page') ?? 0) || 0);
  const [pageSize, setPageSize] = useState(Number(searchParams.get('page_size') ?? 50) || 50);
  const [sort, setSort] = useState(searchParams.get('sort') ?? 'ts_code');
  const [order, setOrder] = useState<'asc' | 'desc'>(
    searchParams.get('order') === 'desc' ? 'desc' : 'asc',
  );

  const [portfolios, setPortfolios] = useState<string[]>([]);
  const [watchlistFor, setWatchlistFor] = useState<string | null>(null);

  useEffect(() => {
    const tmr = setTimeout(() => setDebouncedQ(q.trim()), 300);
    return () => clearTimeout(tmr);
  }, [q]);

  useEffect(() => {
    const params = new URLSearchParams();
    if (debouncedQ) params.set('q', debouncedQ);
    if (industry) params.set('industry', industry);
    if (listStatus !== 'L') params.set('list_status', listStatus);
    if (!excludeSt) params.set('exclude_st', 'false');
    if (activeChip !== 'all') params.set('chip', activeChip);
    if (page > 0) params.set('page', String(page));
    if (pageSize !== 50) params.set('page_size', String(pageSize));
    if (sort !== 'ts_code') params.set('sort', sort);
    if (order !== 'asc') params.set('order', order);
    setSearchParams(params, { replace: true });
  }, [debouncedQ, industry, listStatus, excludeSt, activeChip, page, pageSize, sort, order, setSearchParams]);

  useEffect(() => {
    apiFetch<UniverseMeta>('/api/stocks/universe/meta').then(setMeta).catch(() => {});
    apiFetch<{ portfolios: string[] }>('/api/portfolios')
      .then((d) => setPortfolios(d.portfolios))
      .catch(() => {});
    apiFetch<{ items: IndustrySummaryItem[] }>('/api/stocks/universe/industry-summary?limit=24')
      .then((d) => setIndustrySummary(d.items))
      .catch(() => {});
  }, []);

  const loadUniverse = useCallback(() => {
    const params = new URLSearchParams();
    if (debouncedQ) params.set('q', debouncedQ);
    if (exchange) params.set('exchange', exchange);
    if (market) params.set('market', market);
    if (industry) params.set('industry', industry);
    params.set('list_status', listStatus);
    params.set('exclude_st', String(excludeSt));
    params.set('page', String(page));
    params.set('page_size', String(pageSize));
    params.set('sort', sort);
    params.set('order', order);

    setLoading(true);
    apiFetch<{ total: number; items: StockItem[]; as_of_date: string | null }>(
      `/api/stocks/universe?${params}`,
    )
      .then((data) => {
        setItems(data.items);
        setTotal(data.total);
        setAsOfDate(data.as_of_date);
      })
      .catch((err) => toast.error(err instanceof Error ? err.message : 'Failed to load'))
      .finally(() => setLoading(false));
  }, [debouncedQ, exchange, market, industry, listStatus, excludeSt, page, pageSize, sort, order]);

  useEffect(() => {
    loadUniverse();
  }, [loadUniverse]);

  useEffect(() => {
    setPage(0);
  }, [debouncedQ, exchange, market, industry, listStatus, excludeSt, pageSize]);

  function onChip(chip: Chip) {
    setActiveChip(chip.id);
    setExchange(chip.exchange);
    setMarket(chip.market);
  }

  function toggleSort(col: string) {
    if (sort === col) {
      setOrder(order === 'asc' ? 'desc' : 'asc');
    } else {
      setSort(col);
      setOrder(col === 'pct_chg' || col === 'vol' || col === 'amount' ? 'desc' : 'asc');
    }
  }

  function sortIndicator(col: string) {
    if (sort !== col) return '';
    return order === 'asc' ? ' ↑' : ' ↓';
  }

  function cellValue(row: StockItem, col: (typeof DISPLAY_COLS)[number]) {
    if (col === 'ts_code') return row.ts_code;
    if (col === 'name') return row.name;
    if (col === 'industry') return row.industry ?? '—';
    if (col === 'pct_chg') return formatPct(row.quote?.pct_chg);
    if (col === 'vol') return formatVol(row.quote?.vol);
    if (col === 'amount') return formatAmount(row.quote?.amount);
    return formatPrice(row.quote?.[col as keyof Quote] as number | undefined);
  }

  async function addWatchlist(tsCode: string, portfolioName: string) {
    try {
      await apiFetch(`/api/portfolios/${encodeURIComponent(portfolioName)}/watchlist`, {
        method: 'POST',
        body: JSON.stringify({ ts_code: tsCode }),
      });
      toast.success(t('quote.addedToWatchlist', { code: tsCode, portfolio: portfolioName }));
      setWatchlistFor(null);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed');
    }
  }

  return (
    <div className="page-card stock-list">
      <div className="stock-list-head">
        <h1 className="page-title">{t('nav.quote')}</h1>
        <button
          type="button"
          className="btn btn-secondary btn-sm"
          disabled={items.length === 0}
          onClick={() => exportCsv(items, `quotes-${asOfDate ?? 'page'}.csv`)}
        >
          {t('quote.exportCsv')}
        </button>
      </div>
      <p className="stock-list-meta">
        {asOfDate ? (
          <>
            {t('quote.asOf', { date: asOfDate, count: meta?.listed_count ?? total })}
            <span className="stock-list-delayed"> · {t('quote.delayedData', { date: asOfDate })}</span>
          </>
        ) : (
          t('quote.noQuoteData')
        )}{' '}
        <Link to="/data">{t('quote.syncData')}</Link>
      </p>

      {industrySummary.length > 0 && (
        <div className="stock-list-industry-bar">
          <span className="stock-list-industry-label">{t('quote.industrySummary')}</span>
          <div className="stock-list-industry-scroll">
            {industrySummary.map((item) => (
              <button
                key={item.industry}
                type="button"
                className={`stock-list-industry-chip${industry === item.industry ? ' stock-list-industry-chip--active' : ''}`}
                onClick={() => setIndustry(industry === item.industry ? '' : item.industry)}
              >
                <span>{item.industry}</span>
                <span
                  className={
                    item.avg_pct_chg > 0
                      ? 'stock-list-pct-up'
                      : item.avg_pct_chg < 0
                        ? 'stock-list-pct-down'
                        : ''
                  }
                >
                  {formatPct(item.avg_pct_chg)}
                </span>
              </button>
            ))}
          </div>
        </div>
      )}

      <div className="stock-list-toolbar">
        <div className="form-row" style={{ flex: 1, minWidth: 200, maxWidth: 280, marginBottom: 0 }}>
          <label>{t('quote.search')}</label>
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder={t('quote.searchPlaceholder')}
          />
        </div>
        <div className="form-row" style={{ maxWidth: 160, marginBottom: 0 }}>
          <label>{t('quote.industry')}</label>
          <select value={industry} onChange={(e) => setIndustry(e.target.value)}>
            <option value="">{t('quote.all')}</option>
            {(meta?.industries ?? []).map((ind) => (
              <option key={ind} value={ind}>{ind}</option>
            ))}
          </select>
        </div>
        <div className="form-row" style={{ maxWidth: 120, marginBottom: 0 }}>
          <label>{t('quote.status')}</label>
          <select value={listStatus} onChange={(e) => setListStatus(e.target.value)}>
            <option value="L">{t('quote.listed')}</option>
            <option value="D">{t('quote.delist')}</option>
            <option value="P">{t('quote.pause')}</option>
            <option value="all">{t('quote.all')}</option>
          </select>
        </div>
        <label style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)', fontSize: 'var(--text-sm)' }}>
          <input type="checkbox" checked={excludeSt} onChange={(e) => setExcludeSt(e.target.checked)} />
          {t('quote.hideSt')}
        </label>
      </div>

      <div className="stock-list-chips">
        {CHIPS.map((chip) => (
          <button
            key={chip.id}
            type="button"
            className={`stock-list-chip${activeChip === chip.id ? ' stock-list-chip--active' : ''}`}
            onClick={() => onChip(chip)}
          >
            {t(`quote.chip.${chip.id}`)}
          </button>
        ))}
      </div>

      {total === 0 && !loading ? (
        <p style={{ color: 'var(--color-text-muted)' }}>{t('quote.empty')}</p>
      ) : (
        <>
          <div className="stock-list-table-wrap">
            <table className="data-table stock-list-table">
              <thead>
                <tr>
                  {DISPLAY_COLS.map((col) => (
                    <th
                      key={col}
                      className={SORTABLE.includes(col as (typeof SORTABLE)[number]) ? 'sortable' : undefined}
                      onClick={() => SORTABLE.includes(col as (typeof SORTABLE)[number]) && toggleSort(col)}
                    >
                      {t(`quote.col.${col}`)}
                      {SORTABLE.includes(col as (typeof SORTABLE)[number]) ? sortIndicator(col) : ''}
                    </th>
                  ))}
                  <th>{t('quote.col.actions')}</th>
                </tr>
              </thead>
              <tbody>
                {items.map((row) => (
                  <tr
                    key={row.ts_code}
                    className="stock-list-row"
                    onClick={() => navigate(`/stocks/${encodeURIComponent(row.ts_code)}`)}
                  >
                    {DISPLAY_COLS.map((col) => (
                      <td
                        key={col}
                        className={
                          col === 'pct_chg' && row.quote?.pct_chg != null
                            ? row.quote.pct_chg > 0
                              ? 'stock-list-pct-up'
                              : row.quote.pct_chg < 0
                                ? 'stock-list-pct-down'
                                : ''
                            : undefined
                        }
                      >
                        {cellValue(row, col)}
                      </td>
                    ))}
                    <td onClick={(e) => e.stopPropagation()}>
                      <div className="stock-list-actions">
                        <button
                          type="button"
                          className="btn btn-secondary btn-sm"
                          onClick={() => navigate(`/stocks/${encodeURIComponent(row.ts_code)}`)}
                        >
                          {t('quote.analyze')}
                        </button>
                        {portfolios.length > 0 && (
                          <button
                            type="button"
                            className="btn btn-secondary btn-sm"
                            onClick={() => setWatchlistFor(row.ts_code)}
                          >
                            {t('quote.watchlist')}
                          </button>
                        )}
                      </div>
                      {watchlistFor === row.ts_code && (
                        <div style={{ marginTop: 'var(--space-2)', display: 'flex', gap: 'var(--space-1)', flexWrap: 'wrap' }}>
                          {portfolios.map((p) => (
                            <button
                              key={p}
                              type="button"
                              className="btn btn-sm"
                              onClick={() => addWatchlist(row.ts_code, p)}
                            >
                              {p}
                            </button>
                          ))}
                        </div>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <Pagination
            total={total}
            page={page}
            pageSize={pageSize}
            loading={loading}
            onPageChange={setPage}
            onPageSizeChange={(s) => {
              setPageSize(s);
              setPage(0);
            }}
          />
        </>
      )}
    </div>
  );
}
