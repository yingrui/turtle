import { useCallback, useEffect, useState, type CSSProperties } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { toast } from 'sonner';
import { apiFetch } from '../utils/api';
import { TradeDrawer } from '../components/portfolio/TradeDrawer';
import { DataTable, type Column } from '../components/DataTable';
import { StockDetailDrawer } from '../components/portfolio/StockDetailDrawer';
import { LineChart } from '../components/Chart';
import { usePortfolioContext } from '../contexts/PortfolioContext';
import './Portfolio.scss';

type PortfolioConfig = {
  name?: string;
  follow_stocks?: string[];
  policies?: unknown[];
  risk_control?: Record<string, unknown>;
  initial_investment?: number;
};

type PortfolioStock = {
  ts_code: string;
  status: string;
  hold_shares: number;
  avg_cost: number;
  total_cost: number;
  realized_pnl: number;
  holding_days: number | null;
  first_buy_date: string | null;
  last_trade_date: string | null;
  max_holding_days: number | null;
  stop_loss_point: number | null;
  target_amount: number | null;
  current_price?: number;
  market_value?: number;
  unrealized_pnl?: number;
  unrealized_pct?: number | null;
};

type PortfolioTransaction = {
  id: string;
  ts_code: string;
  side: string;
  shares: number;
  price: number;
  amount: number;
  realized_pnl: number | null;
  trade_date: string;
  source: string;
};

type PoolEntry = {
  ts_code: string;
  rank: number | null;
  score: number | null;
  held: boolean | null;
};

type PortfolioPool = {
  portfolio: string;
  source: 'run' | 'portfolio';
  run_id: string | null;
  pool_mode: 'fixed' | 'dynamic';
  mode: string | null;
  trade_date: string | null;
  pool: PoolEntry[];
  count: number;
};

type PortfolioBenchmark = {
  portfolio: string;
  ts_code: string;
  dates: string[];
  equity: number[];
  benchmark: (number | null)[];
  excess_pct: number | null;
};

type RunSummary = {
  id: string;
  portfolio_name: string;
  mode?: string;
  pool_mode?: string;
  started_at?: string;
  finished_at?: string | null;
};

type TradeDraft = {
  side: 'buy' | 'sell';
  stock: PortfolioStock;
};

export function Portfolio() {
  const { t } = useTranslation();
  const [searchParams, setSearchParams] = useSearchParams();
  // The selected portfolio lives in one place (the context, which also persists it). A second local
  // copy plus two "sync" effects is what made the header and the page fight: each wrote the other's
  // value, so two names alternated on screen.
  const {
    portfolios,
    portfolio: name,
    setPortfolio: setName,
    reload: reloadPortfolios,
  } = usePortfolioContext();
  const [yaml, setYaml] = useState('');
  const [summary, setSummary] = useState<PortfolioConfig | null>(null);
  const [stocks, setStocks] = useState<PortfolioStock[]>([]);
  const [stocksSource, setStocksSource] = useState<'portfolio' | 'run'>('portfolio');
  const [bookDate, setBookDate] = useState<string | null>(null);
  const [bookDates, setBookDates] = useState<string[]>([]);
  const [trades, setTrades] = useState<PortfolioTransaction[]>([]);
  const [pool, setPool] = useState<PortfolioPool | null>(null);
  const [poolDates, setPoolDates] = useState<string[]>([]);
  const [poolDay, setPoolDay] = useState<string | null>(null);
  const [runs, setRuns] = useState<RunSummary[]>([]);
  const [benchmarkCode, setBenchmarkCode] = useState('000300.SH');
  const [benchmarks, setBenchmarks] = useState<{ ts_code: string; name: string }[]>([]);
  const [benchmark, setBenchmark] = useState<PortfolioBenchmark | null>(null);
  const [draft, setDraft] = useState<TradeDraft | null>(null);
  const [tab, setTabState] = useState<'overview' | 'holdings' | 'pool' | 'trades' | 'risk' | 'advanced'>(
    (searchParams.get('tab') as 'overview' | 'holdings' | 'trades' | 'risk' | 'advanced') ?? 'overview',
  );
  const [statusFilter, setStatusFilter] = useState<'watching' | 'holding' | 'closed'>(
    (searchParams.get('status') as 'watching' | 'holding' | 'closed') ?? 'holding',
  );
  const [detail, setDetail] = useState<PortfolioStock | null>(null);
  const [equity, setEquity] = useState<{ dates: string[]; series: { name: string; data: number[] }[] } | null>(null);

  function setTab(next: 'overview' | 'holdings' | 'pool' | 'trades' | 'risk' | 'advanced') {
    setTabState(next);
    const params = new URLSearchParams(searchParams);
    params.set('tab', next);
    if (next === 'holdings') params.set('status', statusFilter);
    else params.delete('status');
    setSearchParams(params, { replace: true });
  }

  function choosePortfolio(next: string) {
    setName(next);
    setBookDate(null);
    const params = new URLSearchParams(searchParams);
    params.set('portfolio', next);
    setSearchParams(params, { replace: true });
  }

  function setStatus(next: 'watching' | 'holding' | 'closed') {
    setStatusFilter(next);
    const params = new URLSearchParams(searchParams);
    params.set('tab', 'holdings');
    params.set('status', next);
    setSearchParams(params, { replace: true });
  }
  const [risk, setRisk] = useState<Record<string, number | boolean> | null>(null);
  const [riskDraft, setRiskDraft] = useState<Record<string, string | boolean>>({});
  const [savingRisk, setSavingRisk] = useState(false);
  const [saving, setSaving] = useState(false);
  const [loadingList, setLoadingList] = useState(true);

  useEffect(() => {
    reloadPortfolios()
      .catch(() => toast.error(t('portfolio.loadError')))
      .finally(() => setLoadingList(false));
  }, [reloadPortfolios, t]);

  // A `?portfolio=` in the URL is an *instruction* to the context, not a second source of truth: it
  // is applied once, and only when it names a portfolio that exists.
  useEffect(() => {
    const fromUrl = searchParams.get('portfolio');
    if (fromUrl && fromUrl !== name && portfolios.includes(fromUrl)) setName(fromUrl);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchParams, portfolios, name]);

  const loadPositions = useCallback(async () => {
    if (!name) return;
    const day = bookDate ? `?day=${encodeURIComponent(bookDate)}` : '';
    const [stockRows, tradeRows, riskRow] = await Promise.all([
      apiFetch<{
        stocks: PortfolioStock[];
        source?: 'portfolio' | 'run';
        trade_date?: string | null;
        available_dates?: string[];
      }>(`/api/portfolios/${encodeURIComponent(name)}/stocks${day}`),
      apiFetch<{ transactions: PortfolioTransaction[] }>(
        `/api/portfolios/${encodeURIComponent(name)}/transactions?limit=50`,
      ),
      apiFetch<Record<string, number | boolean>>(`/api/portfolios/${encodeURIComponent(name)}/risk-control`),
    ]);
    setStocks(stockRows.stocks);
    setStocksSource(stockRows.source === 'run' ? 'run' : 'portfolio');
    setBookDates(stockRows.available_dates ?? []);
    if (stockRows.source === 'run') setBookDate(stockRows.trade_date ?? null);
    setTrades(tradeRows.transactions);
    setRisk(riskRow);
    setRiskDraft(
      Object.fromEntries(Object.entries(riskRow).map(([key, value]) => [key, String(value)])),
    );
  }, [name, bookDate]);

  const loadPool = useCallback(
    async (day?: string | null) => {
      if (!name) return;
      const query = day ? `?day=${encodeURIComponent(day)}` : '';
      const data = await apiFetch<PortfolioPool>(
        `/api/portfolios/${encodeURIComponent(name)}/pool${query}`,
      );
      setPool(data);
      setPoolDay(data.trade_date);
      if (data.pool_mode === 'dynamic' && data.run_id) {
        const dates = await apiFetch<{ dates: string[] }>(
          `/api/simulations/${encodeURIComponent(data.run_id)}/pool-dates`,
        );
        setPoolDates(dates.dates);
      } else {
        setPoolDates([]);
      }
    },
    [name],
  );

  useEffect(() => {
    setBookDate(null);
  }, [name]);

  useEffect(() => {
    if (!name) return;
    apiFetch<{ runs: RunSummary[] }>('/api/simulations')
      .then((d) => setRuns(d.runs.filter((run) => run.portfolio_name === name)))
      .catch(() => setRuns([]));
  }, [name]);

  useEffect(() => {
    apiFetch<{ indexes: { ts_code: string; name: string }[] }>('/api/indexes')
      .then((d) => setBenchmarks((d.indexes ?? []).slice(0, 8)))
      .catch(() => setBenchmarks([]));
  }, []);

  useEffect(() => {
    if (!name || !benchmarkCode) {
      setBenchmark(null);
      return;
    }
    apiFetch<PortfolioBenchmark>(
      `/api/portfolios/${encodeURIComponent(name)}/benchmark?ts_code=${encodeURIComponent(benchmarkCode)}&days=180`,
    )
      .then(setBenchmark)
      .catch(() => setBenchmark(null));   // no trades yet: the chart simply does not appear
  }, [name, benchmarkCode]);

  useEffect(() => {
    if (tab === 'pool') loadPool().catch(() => toast.error(t('portfolio.poolError')));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tab, name]);

  async function activateRun(runId: string | null) {
    try {
      await apiFetch(`/api/portfolios/${encodeURIComponent(name)}/active-run`, {
        method: 'POST',
        body: JSON.stringify({ run_id: runId }),
      });
      await loadPool();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : t('portfolio.poolError'));
    }
  }

  useEffect(() => {
    if (!name) {
      setYaml('');
      setSummary(null);
      setStocks([]);
      setTrades([]);
      setDraft(null);
      return;
    }
    apiFetch<{ yaml: string }>(`/api/portfolios/${encodeURIComponent(name)}/yaml`)
      .then((d) => setYaml(d.yaml))
      .catch(() => toast.error(t('portfolio.loadError')));
    apiFetch<PortfolioConfig>(`/api/portfolios/${encodeURIComponent(name)}`)
      .then(setSummary)
      .catch(() => setSummary(null));
    apiFetch<{ points: { date: string; market_value: number; cost_basis: number }[] }>(
      `/api/portfolios/${encodeURIComponent(name)}/equity?days=180`,
    )
      .then((d) => {
        if (!d.points?.length) {
          setEquity(null);
          return;
        }
        setEquity({
          dates: d.points.map((p) => p.date),
          series: [
            { name: t('portfolio.equityMarketValue'), data: d.points.map((p) => p.market_value) },
            { name: t('portfolio.equityCost'), data: d.points.map((p) => p.cost_basis) },
          ],
        });
      })
      .catch(() => setEquity(null));
    loadPositions().catch(() => {
      setStocks([]);
      setTrades([]);
    });
  }, [name, t, loadPositions]);

  function openTrade(side: 'buy' | 'sell', stock: PortfolioStock) {
    setDraft({ side, stock });
  }

  /** Inline edit of a single numeric column on a holding (PATCH /stocks/{code}). */
  async function patchStock(stock: PortfolioStock, patch: Record<string, number | null>) {
    if (!name) return;
    try {
      const updated = await apiFetch<PortfolioStock>(
        `/api/portfolios/${encodeURIComponent(name)}/stocks/${encodeURIComponent(stock.ts_code)}`,
        { method: 'PATCH', body: JSON.stringify(patch) },
      );
      setStocks((prev) => prev.map((s) => (s.ts_code === updated.ts_code ? { ...s, ...updated } : s)));
      toast.success(t('portfolio.stockUpdated'));
    } catch (err) {
      toast.error(err instanceof Error ? err.message : t('portfolio.stockUpdateFailed'));
    }
  }

  function setRiskValue(key: string, value: string | boolean) {
    setRiskDraft((prev) => ({ ...prev, [key]: value }));
  }

  async function saveRiskControl() {
    if (!name) return;
    const payload: Record<string, number | boolean> = {};
    for (const [key, value] of Object.entries(riskDraft)) {
      const current = risk?.[key];
      if (typeof current === 'boolean') {
        payload[key] = Boolean(value);
      } else if (String(value).trim() !== '') {
        payload[key] = Number(value);
      }
    }
    setSavingRisk(true);
    try {
      const updated = await apiFetch<Record<string, number | boolean>>(
        `/api/portfolios/${encodeURIComponent(name)}/risk-control`,
        { method: 'PUT', body: JSON.stringify({ risk_control: payload }) },
      );
      setRisk(updated);
      setRiskDraft(Object.fromEntries(Object.entries(updated).map(([k, v]) => [k, String(v)])));
      toast.success(t('portfolio.riskSaved'));
    } catch (err) {
      toast.error(err instanceof Error ? err.message : t('portfolio.riskSaveFailed'));
    } finally {
      setSavingRisk(false);
    }
  }

  const policyColumns: Column<Record<string, unknown>>[] = [
    {
      key: 'name',
      label: t('portfolio.policyName'),
      render: (row) => String(row['trade_policy.name'] ?? '—'),
    },
    {
      key: 'params',
      label: t('portfolio.policyParams'),
      render: (row) =>
        Object.entries(row)
          .filter(([key]) => key !== 'trade_policy.name')
          .map(([key, value]) => `${key.replace(/^trade_policy\.[^.]+\./, '')}=${String(value)}`)
          .join('  '),
    },
  ];

  const holdingColumns: Column<PortfolioStock>[] = [
    {
      key: 'ts_code',
      label: t('quote.col.ts_code'),
      render: (row) => <Link to={`/stocks/${encodeURIComponent(row.ts_code)}`}>{row.ts_code}</Link>,
    },
    {
      key: 'status',
      label: t('portfolio.colStatus'),
      render: (row) => statusLabel[row.status] ?? row.status,
    },
    { key: 'shares', label: t('portfolio.colShares'), align: 'right', render: (row) => row.hold_shares },
    { key: 'avg_cost', label: t('portfolio.colAvgCost'), align: 'right', render: (row) => money(row.avg_cost) },
    { key: 'price', label: t('portfolio.colLastPrice'), align: 'right', render: (row) => money(row.current_price) },
    {
      key: 'market_value',
      label: t('portfolio.colMarketValue'),
      align: 'right',
      render: (row) => money(row.market_value),
    },
    {
      key: 'unrealized',
      label: t('portfolio.colUnrealized'),
      align: 'right',
      cellClassName: (row) => ((row.unrealized_pnl ?? 0) < 0 ? 'price-down' : 'price-up'),
      render: (row) => (
        <>
          {money(row.unrealized_pnl)}
          {row.unrealized_pct != null ? ` (${row.unrealized_pct}%)` : ''}
        </>
      ),
    },
    { key: 'total_cost', label: t('portfolio.colTotalCost'), align: 'right', render: (row) => money(row.total_cost) },
    {
      key: 'holding_days',
      label: t('portfolio.colHolding'),
      align: 'right',
      render: (row) => row.holding_days ?? '—',
    },
    {
      key: 'risk',
      label: t('portfolio.colRisk'),
      render: (row) => (
        <span className="portfolio-risk-flags">
          {riskFlags(row).map((flag) => (
            <span key={flag.label} className={`portfolio-flag portfolio-flag--${flag.level}`}>
              {flag.label}
            </span>
          ))}
        </span>
      ),
    },
    {
      key: 'actions',
      label: t('portfolio.colActions'),
      className: 'portfolio-row-actions',
      render: (row) => (
        <>
          <button type="button" className="btn btn-sm" onClick={() => openTrade('buy', row)}>
            {t('portfolio.actionBuy')}
          </button>
          <button
            type="button"
            className="btn btn-sm"
            onClick={() => openTrade('sell', row)}
            disabled={row.hold_shares <= 0}
            title={row.hold_shares <= 0 ? t('portfolio.actionSellDisabled') : undefined}
          >
            {t('portfolio.actionSell')}
          </button>
          <button
            type="button"
            className="btn btn-sm btn-secondary"
            onClick={() => removeStock(row)}
            disabled={row.hold_shares > 0}
            title={row.hold_shares > 0 ? t('portfolio.removeStockBlocked') : undefined}
          >
            {t('portfolio.actionRemove')}
          </button>
        </>
      ),
    },
  ];

  const tradeColumns: Column<PortfolioTransaction>[] = [
    { key: 'date', label: t('portfolio.colTradeDate'), render: (row) => row.trade_date },
    { key: 'ts_code', label: t('quote.col.ts_code'), render: (row) => row.ts_code },
    {
      key: 'side',
      label: t('portfolio.colSide'),
      render: (row) => (row.side === 'buy' ? t('portfolio.sideBuy') : t('portfolio.sideSell')),
    },
    { key: 'shares', label: t('portfolio.colShares'), align: 'right', render: (row) => row.shares },
    { key: 'price', label: t('portfolio.colPrice'), align: 'right', render: (row) => money(row.price) },
    { key: 'amount', label: t('portfolio.colAmount'), align: 'right', render: (row) => money(row.amount) },
    {
      key: 'realized',
      label: t('portfolio.colRealized'),
      align: 'right',
      cellClassName: (row) => ((row.realized_pnl ?? 0) < 0 ? 'price-down' : 'price-up'),
      render: (row) => money(row.realized_pnl),
    },
    {
      key: 'source',
      label: t('portfolio.colSource'),
      render: (row) => sourceLabel[row.source] ?? row.source,
    },
  ];

  const poolColumns: Column<PoolEntry>[] = [
    {
      key: 'ts_code',
      label: t('quote.col.ts_code'),
      sortable: true,
      sortValue: (row) => row.ts_code,
      render: (row) => <Link to={`/stocks/${encodeURIComponent(row.ts_code)}`}>{row.ts_code}</Link>,
    },
    {
      key: 'rank',
      label: t('portfolio.poolColRank'),
      align: 'right',
      sortable: true,
      sortValue: (row) => row.rank ?? 0,
      render: (row) => (row.rank ? row.rank : '—'),
    },
    {
      key: 'score',
      label: t('portfolio.poolColScore'),
      align: 'right',
      sortable: true,
      sortValue: (row) => row.score ?? 0,
      render: (row) => (row.score == null ? '—' : row.score.toFixed(3)),
    },
    {
      key: 'held',
      label: t('portfolio.poolColHeld'),
      render: (row) =>
        row.held == null ? '—' : row.held ? t('portfolio.poolHeld') : t('portfolio.poolWatching'),
    },
  ];

  const holdings = stocks.filter((s) => s.status === 'holding' && s.hold_shares > 0);
  const totalMarketValue = holdings.reduce((sum, s) => sum + (s.market_value ?? 0), 0);
  const totalCost = holdings.reduce((sum, s) => sum + s.total_cost, 0);
  const unrealized = holdings.reduce((sum, s) => sum + (s.unrealized_pnl ?? 0), 0);
  const realized = stocks.reduce((sum, s) => sum + s.realized_pnl, 0);
  const unrealizedPct = totalCost > 0 ? (unrealized / totalCost) * 100 : null;

  /** Risk hints per holding: stop-loss distance, holding-period budget, position weight. */
  function riskFlags(stock: PortfolioStock): { level: 'warn' | 'danger'; label: string }[] {
    const flags: { level: 'warn' | 'danger'; label: string }[] = [];
    const price = stock.current_price;
    if (price != null && stock.stop_loss_point != null && price <= stock.stop_loss_point) {
      flags.push({ level: 'danger', label: t('portfolio.riskBrokenStop') });
    } else if (price != null && stock.stop_loss_point != null) {
      const distance = (price - stock.stop_loss_point) / price;
      if (distance <= 0.03) flags.push({ level: 'warn', label: t('portfolio.riskNearStop') });
    }
    const maxDays = stock.max_holding_days ?? (risk?.['max_holding_period.days'] as number | undefined);
    const checkPeriod = risk?.['max_holding_period.should_check'] !== false;
    if (checkPeriod && maxDays && stock.holding_days != null) {
      const remaining = maxDays - stock.holding_days;
      if (remaining <= 0) flags.push({ level: 'danger', label: t('portfolio.riskOverHolding') });
      else if (remaining <= 5) flags.push({ level: 'warn', label: t('portfolio.riskHoldingDue') });
    }
    const ratio = risk?.['max_position_ratio'] as number | undefined;
    if (ratio && totalMarketValue > 0 && (stock.market_value ?? 0) / totalMarketValue > ratio) {
      flags.push({ level: 'warn', label: t('portfolio.riskOverWeight') });
    }
    return flags;
  }

  async function removeStock(stock: PortfolioStock) {
    if (!name) return;
    if (!window.confirm(t('portfolio.removeStockConfirm', { code: stock.ts_code }))) return;
    try {
      await apiFetch(
        `/api/portfolios/${encodeURIComponent(name)}/stocks/${encodeURIComponent(stock.ts_code)}`,
        { method: 'DELETE' },
      );
      toast.success(t('portfolio.removeStockDone', { code: stock.ts_code }));
      await loadPositions();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : t('portfolio.removeStockFailed'));
    }
  }

  const statusLabel: Record<string, string> = {
    watching: t('portfolio.statusWatching'),
    holding: t('portfolio.statusHolding'),
    closed: t('portfolio.statusClosed'),
  };
  const sourceLabel: Record<string, string> = {
    manual: t('portfolio.sourceManual'),
    simulation: t('portfolio.sourceSimulation'),
    import: t('portfolio.sourceImport'),
  };
  const money = (v: number | null | undefined) =>
    v === null || v === undefined ? '—' : v.toLocaleString(undefined, { maximumFractionDigits: 2 });

  async function onSave() {
    setSaving(true);
    try {
      await apiFetch(`/api/portfolios/${encodeURIComponent(name)}/yaml`, {
        method: 'PUT',
        body: JSON.stringify({ yaml }),
      });
      toast.success(t('portfolio.saved'));
      const cfg = await apiFetch<PortfolioConfig>(`/api/portfolios/${encodeURIComponent(name)}`);
      setSummary(cfg);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : t('portfolio.saveFailed'));
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="page-card portfolio-page">
      <p className="portfolio-breadcrumb">
        <Link to={name ? `/watchlist?portfolio=${encodeURIComponent(name)}` : '/watchlist'}>
          ← {t('nav.watchlist')}
        </Link>
      </p>
      <h1 className="page-title">{t('portfolio.configPageTitle')}</h1>
      <p className="portfolio-intro">{t('portfolio.configPageDesc')}</p>

      {loadingList ? (
        <p className="portfolio-muted">{t('portfolio.loading')}</p>
      ) : portfolios.length === 0 ? (
        <div className="portfolio-empty">
          <p className="portfolio-muted">{t('portfolio.noPortfolioForConfig')}</p>
          <Link to="/watchlist" className="btn btn-primary">
            {t('watchlist.createPortfolio')}
          </Link>
        </div>
      ) : (
        <>
          {/* The portfolio is chosen here, where it means something: other pages read the same value
              from the context but do not need a control of their own. */}
          <div className="form-row field-wide mb-4">
            <label htmlFor="portfolio-config-select">{t('portfolio.select')}</label>
            <select
              id="portfolio-config-select"
              value={name}
              onChange={(e) => choosePortfolio(e.target.value)}
            >
              {portfolios.map((p) => (
                <option key={p} value={p}>{p}</option>
              ))}
            </select>
          </div>

          {name && summary && (
            <section className="portfolio-editor">
              <nav className="portfolio-tabs" role="tablist">
                {(
                  [
                    ['overview', t('portfolio.tabOverview')],
                    ['holdings', t('portfolio.tabHoldings')],
                    ['pool', t('portfolio.tabPool')],
                    ['trades', t('portfolio.tabTrades')],
                    ['risk', t('portfolio.tabRisk')],
                    ['advanced', t('portfolio.tabAdvanced')],
                  ] as const
                ).map(([key, label]) => (
                  <button
                    key={key}
                    type="button"
                    role="tab"
                    aria-selected={tab === key}
                    className={tab === key ? 'portfolio-tab portfolio-tab--active' : 'portfolio-tab'}
                    onClick={() => setTab(key)}
                  >
                    {label}
                  </button>
                ))}
              </nav>

              {tab === 'overview' && (
                <>
                  {equity && (
                    <section className="portfolio-equity">
                      <h2 className="portfolio-panel-title">{t('portfolio.equityTitle')}</h2>
                      <p className="portfolio-panel-desc">{t('portfolio.equityDesc')}</p>
                      <LineChart data={equity} />
                    </section>
                  )}

                  {benchmark && benchmark.dates.length > 0 && (
                    <section className="portfolio-equity">
                      <div className="split-row">
                        <div>
                          <h2 className="portfolio-panel-title">{t('portfolio.benchmarkTitle')}</h2>
                          <p className="portfolio-panel-desc">{t('portfolio.benchmarkDesc')}</p>
                        </div>
                        <div className="form-row field-medium">
                          <label htmlFor="portfolio-benchmark">{t('results.benchmark')}</label>
                          <select
                            id="portfolio-benchmark"
                            value={benchmarkCode}
                            onChange={(e) => setBenchmarkCode(e.target.value)}
                          >
                            {benchmarks.map((item) => (
                              <option key={item.ts_code} value={item.ts_code}>
                                {item.name}
                              </option>
                            ))}
                          </select>
                        </div>
                      </div>
                      {benchmark.excess_pct != null && (
                        <p className={`text-sm ${benchmark.excess_pct >= 0 ? 'price-up' : 'price-down'}`}>
                          {t('results.excessVsBenchmark', { value: benchmark.excess_pct.toFixed(2) })}
                        </p>
                      )}
                      <LineChart
                        data={{
                          dates: benchmark.dates,
                          series: [
                            {
                              name: t('portfolio.benchmarkEquity'),
                              data: benchmark.equity as (number | null)[],
                            },
                            { name: benchmark.ts_code, data: benchmark.benchmark },
                          ],
                        }}
                      />
                    </section>
                  )}
                  <div className="stat-grid">
                    <div className="stat-card">
                      <span>{t('portfolio.kpiHoldings')}</span>
                      <strong>{holdings.length}</strong>
                    </div>
                    <div className="stat-card">
                      <span>{t('portfolio.kpiWatching')}</span>
                      <strong>{stocks.filter((s) => s.status === 'watching').length}</strong>
                    </div>
                    <div className="stat-card">
                      <span>{t('portfolio.kpiMarketValue')}</span>
                      <strong>{money(totalMarketValue)}</strong>
                    </div>
                    <div className="stat-card">
                      <span>{t('portfolio.kpiCost')}</span>
                      <strong>{money(totalCost)}</strong>
                    </div>
                    <div className="stat-card">
                      <span>{t('portfolio.kpiUnrealized')}</span>
                      <strong className={unrealized < 0 ? 'price-down' : 'price-up'}>
                        {money(unrealized)}
                        {unrealizedPct != null ? ` (${unrealizedPct.toFixed(2)}%)` : ''}
                      </strong>
                    </div>
                    <div className="stat-card">
                      <span>{t('portfolio.kpiRealized')}</span>
                      <strong className={realized < 0 ? 'price-down' : 'price-up'}>{money(realized)}</strong>
                    </div>
                    <div className="stat-card">
                      <span>{t('portfolio.statCapital')}</span>
                      <strong>{summary.initial_investment?.toLocaleString() ?? '—'}</strong>
                    </div>
                  </div>
                  {stocks.length > 0 && totalMarketValue > 0 && (
                    <>
                      <h2 className="portfolio-panel-title">{t('portfolio.weightsTitle')}</h2>
                      <ul className="portfolio-weights">
                        {holdings.map((s) => (
                          <li key={s.ts_code}>
                            <span className="portfolio-weight-code">{s.ts_code}</span>
                            <span className="portfolio-weight-bar">
                              {/* Geometry comes from the stylesheet; only the number crosses over. */}
                              <span
                                className="portfolio-weight-fill"
                                style={{ '--fill': `${(((s.market_value ?? 0) / totalMarketValue) * 100).toFixed(1)}%` } as CSSProperties}
                              />
                            </span>
                            <span className="portfolio-weight-pct">
                              {(((s.market_value ?? 0) / totalMarketValue) * 100).toFixed(1)}%
                            </span>
                          </li>
                        ))}
                      </ul>

                      <h2 className="portfolio-panel-title">{t('portfolio.pnlTitle')}</h2>
                      <p className="portfolio-panel-desc">{t('portfolio.pnlDesc')}</p>
                      <ul className="portfolio-bullets">
                        {holdings.map((s) => {
                          const price = s.current_price ?? s.avg_cost;
                          const cost = s.avg_cost;
                          const stop = s.stop_loss_point;
                          const values = [cost, price, ...(stop != null ? [stop] : [])];
                          const lo = Math.min(...values);
                          const hi = Math.max(...values);
                          const span = hi - lo || 1;
                          const pos = (v: number) => ((v - lo) / span) * 100;
                          const fillLeft = Math.min(pos(cost), pos(price));
                          const fillWidth = Math.abs(pos(price) - pos(cost));
                          const gain = (s.unrealized_pnl ?? 0) >= 0;
                          return (
                            <li key={s.ts_code}>
                              <span className="portfolio-weight-code">{s.ts_code}</span>
                              <span className="portfolio-bullet">
                                <span
                                  className={`portfolio-bullet-fill ${gain ? 'price-up-bg' : 'price-down-bg'}`}
                                  style={{ '--from': `${fillLeft}%`, '--width': `${fillWidth}%` } as CSSProperties}
                                />
                                <span
                                  className="portfolio-bullet-mark portfolio-bullet-mark--cost"
                                  style={{ '--at': `${pos(cost)}%` } as CSSProperties}
                                />
                                {stop != null && (
                                  <span
                                    className="portfolio-bullet-mark portfolio-bullet-mark--stop"
                                    style={{ '--at': `${pos(stop)}%` } as CSSProperties}
                                  />
                                )}
                                <span
                                  className="portfolio-bullet-mark portfolio-bullet-mark--price"
                                  style={{ '--at': `${pos(price)}%` } as CSSProperties}
                                />
                              </span>
                              <span className={`portfolio-weight-pct ${gain ? 'price-up' : 'price-down'}`}>
                                {money(s.unrealized_pnl)}
                              </span>
                            </li>
                          );
                        })}
                      </ul>
                      <p className="portfolio-legend">{t('portfolio.bulletLegend')}</p>
                    </>
                  )}

                  <div className="portfolio-save-row">
                    <Link className="btn btn-secondary" to={`/simulation?portfolio=${encodeURIComponent(name)}`}>
                      {t('portfolio.runBacktest')}
                    </Link>
                    <Link className="btn btn-secondary" to={`/watchlist?portfolio=${encodeURIComponent(name)}`}>
                      {t('portfolio.viewWatchlist')}
                    </Link>
                  </div>
                </>
              )}

              {tab === 'holdings' && (
                <>
              <h2 className="portfolio-panel-title">{t('portfolio.holdingsTitle')}</h2>
              <p className="portfolio-panel-desc">{t('portfolio.holdingsDesc')}</p>
              {stocksSource === 'run' && (
                <div className="form-row field-medium">
                  <label>{t('portfolio.poolDate')}</label>
                  <select
                    value={bookDate ?? ''}
                    onChange={(e) => {
                      setBookDate(e.target.value);
                      loadPositions().catch(() => toast.error(t('portfolio.loadError')));
                    }}
                  >
                    {bookDates.map((d) => (
                      <option key={d} value={d}>{d}</option>
                    ))}
                  </select>
                </div>
              )}
              {stocksSource === 'run' ? null : (
              <div className="portfolio-segments" role="group" aria-label={t('portfolio.colStatus')}>
                {(['watching', 'holding', 'closed'] as const).map((key) => (
                  <button
                    key={key}
                    type="button"
                    className={statusFilter === key ? 'portfolio-segment portfolio-segment--active' : 'portfolio-segment'}
                    onClick={() => setStatus(key)}
                  >
                    {statusLabel[key]}
                    <span className="portfolio-segment-count">
                      {stocks.filter((row) => row.status === key).length}
                    </span>
                  </button>
                ))}
              </div>
              )}
              <DataTable
                pageSize={25}
                columns={holdingColumns}
                rows={stocksSource === 'run' ? stocks : stocks.filter((row) => row.status === statusFilter)}
                onRowClick={(row) => setDetail(row)}
                rowKey={(row) => row.ts_code}
                empty={
                  <>
                    {t('portfolio.emptyHoldings')} <Link to="/screening">{t('portfolio.emptyHoldingsCta')}</Link>
                  </>
                }
              />
                </>
              )}

              {tab === 'pool' && (
                <>
                  <h2 className="portfolio-panel-title">{t('portfolio.poolTitle')}</h2>
                  <p className="portfolio-panel-desc">{t('portfolio.poolDesc')}</p>
                  <div className="form-row field-xwide">
                    <label>{t('portfolio.poolRun')}</label>
                    <select
                      value={pool?.run_id ?? ''}
                      onChange={(e) => activateRun(e.target.value || null)}
                    >
                      <option value="">{t('portfolio.poolFromWatchlist')}</option>
                      {runs.map((run) => (
                        <option key={run.id} value={run.id}>
                          {(run.finished_at ?? run.started_at ?? '').slice(0, 10)} · {run.mode ?? 'signal'}/
                          {run.pool_mode ?? 'fixed'} · {run.id.slice(0, 8)}
                        </option>
                      ))}
                    </select>
                  </div>
                  {pool && (
                    <>
                      <p className="text-hint">
                        {t('portfolio.poolMeta', {
                          source: pool.source === 'run' ? t('portfolio.poolSourceRun') : t('portfolio.poolSourceList'),
                          mode: pool.pool_mode,
                          date: pool.trade_date ?? '—',
                          count: pool.count,
                        })}
                      </p>
                      {pool.pool_mode === 'dynamic' && poolDates.length > 0 && (
                        <div className="form-row field-medium">
                          <label>{t('portfolio.poolDate')}</label>
                          <select value={poolDay ?? ''} onChange={(e) => loadPool(e.target.value)}>
                            {poolDates.map((d) => (
                              <option key={d} value={d}>{d}</option>
                            ))}
                          </select>
                        </div>
                      )}
                      <DataTable
                        pageSize={25}
                        columns={poolColumns}
                        rows={pool.pool}
                        rowKey={(row) => row.ts_code}
                        empty={t('portfolio.poolEmpty')}
                        defaultSortCol="rank"
                      />
                    </>
                  )}
                </>
              )}

              {tab === 'trades' && (
                <>
              <h2 className="portfolio-panel-title">{t('portfolio.tradesTitle')}</h2>
              <p className="portfolio-panel-desc">{t('portfolio.tradesDesc')}</p>
              <DataTable
                pageSize={25}
                columns={tradeColumns}
                rows={trades}
                rowKey={(row) => row.id}
                empty={t('portfolio.emptyTrades')}
              />
                </>
              )}

              {tab === 'risk' && (
                <>
                  <h2 className="portfolio-panel-title">{t('portfolio.riskTitle')}</h2>
                  <p className="portfolio-panel-desc">{t('portfolio.riskDesc')}</p>
                  <div className="portfolio-risk-form">
                    {[
                      ['bearable_trading_loss', 'riskBearableLoss'],
                      ['position_control', 'riskPositionControl'],
                      ['position_control.reserve_profit', 'riskReserveProfit'],
                      ['max_position_size', 'riskMaxPositionSize'],
                      ['max_position_ratio', 'riskMaxPositionRatio'],
                      ['stop_loss_point.n_times_atr', 'riskStopLossAtr'],
                      ['max_holding_period.days', 'riskMaxHoldingDays'],
                    ].map(([key, label]) => (
                      <label key={key} className="portfolio-risk-field" htmlFor={`risk-${key}`}>
                        <span>{t(`portfolio.${label}`)}</span>
                        <input
                          id={`risk-${key}`}
                          type="number"
                          step="any"
                          value={String(riskDraft[key] ?? '')}
                          onChange={(e) => setRiskValue(key, e.target.value)}
                        />
                      </label>
                    ))}
                    {[
                      ['stop_loss_point.should_check', 'riskStopLossCheck'],
                      ['stop_loss_point.should_update', 'riskStopLossUpdate'],
                      ['max_holding_period.should_check', 'riskMaxHoldingCheck'],
                    ].map(([key, label]) => (
                      <label key={key} className="portfolio-risk-toggle" htmlFor={`risk-${key}`}>
                        <input
                          id={`risk-${key}`}
                          type="checkbox"
                          checked={Boolean(riskDraft[key])}
                          onChange={(e) => setRiskValue(key, e.target.checked)}
                        />
                        <span>{t(`portfolio.${label}`)}</span>
                      </label>
                    ))}
                  </div>
                  <div className="portfolio-save-row">
                    <button
                      type="button"
                      className="btn btn-primary"
                      onClick={saveRiskControl}
                      disabled={savingRisk || !risk}
                    >
                      {savingRisk ? t('portfolio.saving') : t('portfolio.save')}
                    </button>
                  </div>

                  <h2 className="portfolio-panel-title">{t('portfolio.policiesTitle')}</h2>
                  <p className="portfolio-panel-desc">{t('portfolio.policiesDesc')}</p>
                  <DataTable
                    columns={policyColumns}
                    rows={summary.policies as Record<string, unknown>[]}
                    rowKey={(row) => String(row['trade_policy.name'] ?? '')}
                    empty={t('portfolio.policiesEmpty')}
                  />
                </>
              )}

              {tab === 'advanced' && (
                <>
              <h2 className="portfolio-panel-title">{t('portfolio.configTitle')}</h2>
              <p className="portfolio-panel-desc">{t('portfolio.configDesc')}</p>
              <textarea
                className="yaml-editor"
                value={yaml}
                onChange={(e) => setYaml(e.target.value)}
                spellCheck={false}
                aria-label={t('portfolio.configTitle')}
              />
              <div className="portfolio-save-row">
                <button
                  type="button"
                  className="btn btn-primary"
                  onClick={onSave}
                  disabled={saving || !yaml}
                >
                  {saving ? t('portfolio.saving') : t('portfolio.save')}
                </button>
              </div>
                </>
              )}
            </section>
          )}
        </>
      )}

      {detail && (
        <StockDetailDrawer
          stock={detail}
          flags={riskFlags(detail)}
          money={money}
          onClose={() => setDetail(null)}
          onPatch={(patch) => patchStock(detail, patch)}
          onTrade={(side) => {
            const target = detail;
            setDetail(null);
            openTrade(side, target);
          }}
        />
      )}

      {draft && name && (
        <TradeDrawer
          portfolio={name}
          target={{
            ts_code: draft.stock.ts_code,
            avg_cost: draft.stock.avg_cost,
            current_price: draft.stock.current_price,
            hold_shares: draft.stock.hold_shares,
          }}
          initialSide={draft.side}
          onClose={() => setDraft(null)}
          onSaved={() => {
            loadPositions().catch(() => {});
          }}
        />
      )}
    </div>
  );
}
