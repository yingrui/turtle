import { useCallback, useEffect, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { RunHoldingsPanel, type RunHolding } from '../components/portfolio/RunHoldingsPanel';
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



type PortfolioBenchmark = {
  portfolio: string;
  ts_code: string;
  dates: string[];
  equity: number[];
  benchmark: (number | null)[];
  excess_pct: number | null;
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
  const [summary, setSummary] = useState<PortfolioConfig | null>(null);
  const [stocks, setStocks] = useState<PortfolioStock[]>([]);
  const [bookDate, setBookDate] = useState<string | null>(null);
  const [trades, setTrades] = useState<PortfolioTransaction[]>([]);
  const [benchmarkCode, setBenchmarkCode] = useState('000300.SH');
  const [benchmarks, setBenchmarks] = useState<{ ts_code: string; name: string }[]>([]);
  const [benchmark, setBenchmark] = useState<PortfolioBenchmark | null>(null);
  const [draft, setDraft] = useState<TradeDraft | null>(null);
  const [tab, setTabState] = useState<'overview' | 'holdings' | 'trades' | 'risk'>(
    (searchParams.get('tab') as 'overview' | 'holdings' | 'trades' | 'risk') ?? 'overview',
  );
  const [detail, setDetail] = useState<PortfolioStock | null>(null);
  const [runs, setRuns] = useState<{
    id: string;
    name: string | null;
    portfolio_name: string;
    window_start: string | null;
    window_end: string | null;
  }[]>([]);
  const [runId, setRunId] = useState('');
  const [runDays, setRunDays] = useState<string[]>([]);
  const [runDay, setRunDay] = useState('');
  const [runHoldings, setRunHoldings] = useState<RunHolding[]>([]);
  const [runCash, setRunCash] = useState<number | null>(null);
  const [runTrades, setRunTrades] = useState<
    { id: string; date: string; ts_code: string; side: string; shares: number; price: number; amount: number; benefit: number }[]
  >([]);
  const [equity, setEquity] = useState<{ dates: string[]; series: { name: string; data: number[] }[] } | null>(null);

  function setTab(next: 'overview' | 'holdings' | 'trades' | 'risk') {
    setTabState(next);
    const params = new URLSearchParams(searchParams);
    params.set('tab', next);
    setSearchParams(params, { replace: true });
  }

  function choosePortfolio(next: string) {
    setName(next);
    setBookDate(null);
    const params = new URLSearchParams(searchParams);
    params.set('portfolio', next);
    setSearchParams(params, { replace: true });
  }

  const [risk, setRisk] = useState<Record<string, number | boolean> | null>(null);
  const [riskDraft, setRiskDraft] = useState<Record<string, string | boolean>>({});
  const [savingRisk, setSavingRisk] = useState(false);
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
    if (stockRows.source === 'run') setBookDate(stockRows.trade_date ?? null);
    setTrades(tradeRows.transactions);
    setRisk(riskRow);
    setRiskDraft(
      Object.fromEntries(Object.entries(riskRow).map(([key, value]) => [key, String(value)])),
    );
  }, [name, bookDate]);


  useEffect(() => {
    setBookDate(null);
    apiFetch<{ runs: { id: string; name: string | null; portfolio_name: string; window_start: string | null; window_end: string | null; finished_at: string | null }[] }>('/api/simulations')
      .then((d) => {
        // Only this portfolio's finished runs: the list is global, the question is not.
        const mine = (d.runs ?? []).filter((run) => run.finished_at && run.portfolio_name === name);
        setRuns(mine);
        setRunId(mine[0]?.id ?? '');
      })
      .catch(() => setRuns([]));
  }, [name]);

  useEffect(() => {
    if (!runId) {
      setRunDays([]);
      setRunHoldings([]);
      return;
    }
    apiFetch<{ dates: string[] }>(`/api/simulations/${runId}/holding-dates`)
      .then((d) => {
        const days = d.dates ?? [];
        setRunDays(days);
        setRunDay(days[days.length - 1] ?? '');
      })
      .catch(() => setRunDays([]));
  }, [runId]);

  useEffect(() => {
    if (!runId || !runDay) {
      setRunHoldings([]);
      return;
    }
    apiFetch<{ holdings: RunHolding[]; cash?: number | null }>(`/api/simulations/${runId}/holdings?day=${encodeURIComponent(runDay)}`)
      .then((d) => {
        setRunHoldings(d.holdings ?? []);
        setRunCash(d.cash ?? null);
      })
      .catch(() => setRunHoldings([]));
    apiFetch<{ trades: { date: string; ts_code: string; side: string; shares: number; price: number; amount: number; benefit: number }[] }>(
      `/api/simulations/${runId}/trades?limit=500`,
    )
      .then((d) =>
        setRunTrades(
          (d.trades ?? []).map((trade, index) => ({ id: `${trade.date}-${trade.ts_code}-${index}`, ...trade })),
        ),
      )
      .catch(() => setRunTrades([]));
  }, [runId, runDay]);


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
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tab, name]);


  useEffect(() => {
    if (!name) {
      setSummary(null);
      setStocks([]);
      setTrades([]);
      setDraft(null);
      return;
    }
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


  const holdings = stocks.filter((s) => s.status === 'holding' && s.hold_shares > 0);
  // A portfolio with no manual records has nothing to sum; its numbers are the selected run's.
  const bookRows = runHoldings.length > 0 ? runHoldings : [];
  const totalMarketValue = bookRows.length
    ? bookRows.reduce((sum, row) => sum + row.shares * row.price, 0)
    : holdings.reduce((sum, s) => sum + (s.market_value ?? 0), 0);
  const totalCost = bookRows.length
    ? bookRows.reduce((sum, row) => sum + (row.avg_cost ?? row.price) * row.shares, 0)
    : holdings.reduce((sum, s) => sum + s.total_cost, 0);
  const unrealized = bookRows.length
    ? bookRows.reduce((sum, row) => sum + (row.unrealized_pnl ?? 0), 0)
    : holdings.reduce((sum, s) => sum + (s.unrealized_pnl ?? 0), 0);
  // Realised profit lives in the run's sell fills; the manual ledger has none for a research portfolio.
  // Realised is cumulative **up to the selected day**: summing the whole run would count sales that
  // have not happened yet at the date being looked at, and the two numbers would never tie out.
  const realized = bookRows.length
    ? runTrades.reduce(
        (sum, trade) => sum + (trade.side === 'sell' && trade.date <= runDay ? trade.benefit : 0),
        0,
      )
    : stocks.reduce((sum, s) => sum + s.realized_pnl, 0);
  const unrealizedPct = totalCost > 0 ? (unrealized / totalCost) * 100 : null;
  // What a broker shows as the account's gain this period: the held positions and the closed ones
  // together. Both are already net of fees (the average cost includes buy fees, the realised figure
  // subtracts sell fees), so this needs no further adjustment.
  const cumulative = unrealized + realized;

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

  const sourceLabel: Record<string, string> = {
    manual: t('portfolio.sourceManual'),
    simulation: t('portfolio.sourceSimulation'),
    import: t('portfolio.sourceImport'),
  };
  const money = (v: number | null | undefined) =>
    v === null || v === undefined ? '—' : v.toLocaleString(undefined, { maximumFractionDigits: 2 });


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
          <div className="toolbar mb-4">
            <div className="form-row field-wide">
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
            <div className="form-row field-wide">
              <label htmlFor="portfolio-run-select">{t('portfolio.pickRun')}</label>
              <select id="portfolio-run-select" value={runId} onChange={(e) => setRunId(e.target.value)}>
                {runs.length === 0 && (
                  <option value="">{t('portfolio.noRuns')}</option>
                )}
                {runs.map((run) => (
                  <option key={run.id} value={run.id}>
                    {run.name || run.id.slice(0, 8)} · {run.window_start ?? '—'} → {run.window_end ?? '—'}
                  </option>
                ))}
              </select>
            </div>
            <div className="form-row field-medium">
              <label htmlFor="portfolio-day-select">{t('portfolio.pickDay')}</label>
              <select id="portfolio-day-select" value={runDay} onChange={(e) => setRunDay(e.target.value)}>
                {runDays.slice().reverse().map((day) => (
                  <option key={day} value={day}>{day}</option>
                ))}
              </select>
            </div>
          </div>

          {name && summary && (
            <section className="portfolio-editor">
              <nav className="portfolio-tabs" role="tablist">
                {(
                  [
                    ['overview', t('portfolio.tabOverview')],
                    ['holdings', t('portfolio.tabHoldings')],
                    ['trades', t('portfolio.tabTrades')],
                    ['risk', t('portfolio.tabRisk')],
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
                      <strong>{bookRows.length || holdings.length}</strong>
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
                      <span>{t('portfolio.kpiCumulative')}</span>
                      <strong className={cumulative < 0 ? 'price-down' : 'price-up'}>{money(cumulative)}</strong>
                    </div>
                    <div className="stat-card">
                      <span>{t('portfolio.kpiCash')}</span>
                      <strong>{runCash == null ? '—' : money(runCash)}</strong>
                    </div>
                    <div className="stat-card">
                      <span>{t('portfolio.statCapital')}</span>
                      <strong>{summary.initial_investment?.toLocaleString() ?? '—'}</strong>
                    </div>
                  </div>
                  <p className="portfolio-panel-desc">{t('portfolio.statNote')}</p>
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

              {tab === 'holdings' && <RunHoldingsPanel rows={runHoldings} day={runDay} />}

              {tab === 'trades' && (
                <>
                  <h2 className="portfolio-panel-title">{t('portfolio.tradesTitle')}</h2>
                  <p className="portfolio-panel-desc">{t('portfolio.tradesDesc')}</p>
                  {runTrades.length > 0 ? (
                    <DataTable
                      pageSize={25}
                      columns={[
                        { key: 'date', label: t('portfolio.colDate'), render: (row) => row.date },
                        { key: 'code', label: t('portfolio.colCode'), render: (row) => row.ts_code },
                        {
                          key: 'side',
                          label: t('portfolio.colSide'),
                          render: (row) => (row.side === 'buy' ? t('portfolio.sideBuy') : t('portfolio.sideSell')),
                        },
                        { key: 'shares', label: t('portfolio.colShares'), align: 'right', render: (row) => row.shares },
                        { key: 'price', label: t('portfolio.colPrice'), align: 'right', render: (row) => money(row.price) },
                        { key: 'amount', label: t('portfolio.colAmount'), align: 'right', render: (row) => money(row.amount) },
                        {
                          key: 'benefit',
                          label: t('portfolio.colRealized'),
                          align: 'right',
                          cellClassName: (row) => (row.benefit < 0 ? 'price-down' : 'price-up'),
                          render: (row) => (row.side === 'sell' ? money(row.benefit) : '—'),
                        },
                      ]}
                      rows={runTrades}
                      rowKey={(row) => row.id}
                      empty={t('portfolio.emptyTrades')}
                    />
                  ) : (
                    <DataTable
                      pageSize={25}
                      columns={tradeColumns}
                      rows={trades}
                      rowKey={(row) => row.id}
                      empty={t('portfolio.emptyTrades')}
                    />
                  )}
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
