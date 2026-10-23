import { useCallback, useEffect, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { toast } from 'sonner';
import { apiFetch } from '../utils/api';
import { TradeDrawer } from '../components/portfolio/TradeDrawer';
import { DataTable, type Column } from '../components/DataTable';
import { StockDetailDrawer } from '../components/portfolio/StockDetailDrawer';
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
  simulation_run_id: string | null;
};

type TradeDraft = {
  side: 'buy' | 'sell';
  stock: PortfolioStock;
};

export function Portfolio() {
  const { t } = useTranslation();
  const [searchParams, setSearchParams] = useSearchParams();
  const [portfolios, setPortfolios] = useState<string[]>([]);
  const [name, setName] = useState(searchParams.get('portfolio') ?? '');
  const [yaml, setYaml] = useState('');
  const [summary, setSummary] = useState<PortfolioConfig | null>(null);
  const [stocks, setStocks] = useState<PortfolioStock[]>([]);
  const [trades, setTrades] = useState<PortfolioTransaction[]>([]);
  const [draft, setDraft] = useState<TradeDraft | null>(null);
  const { portfolio: ctxPortfolio, setPortfolio: setCtxPortfolio } = usePortfolioContext();
  const [tab, setTabState] = useState<'overview' | 'holdings' | 'trades' | 'risk' | 'advanced'>(
    (searchParams.get('tab') as 'overview' | 'holdings' | 'trades' | 'risk' | 'advanced') ?? 'overview',
  );
  const [statusFilter, setStatusFilter] = useState<'watching' | 'holding' | 'closed'>(
    (searchParams.get('status') as 'watching' | 'holding' | 'closed') ?? 'holding',
  );
  const [detail, setDetail] = useState<PortfolioStock | null>(null);

  function setTab(next: 'overview' | 'holdings' | 'trades' | 'risk' | 'advanced') {
    setTabState(next);
    const params = new URLSearchParams(searchParams);
    params.set('tab', next);
    if (next === 'holdings') params.set('status', statusFilter);
    else params.delete('status');
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

  const loadList = useCallback(async () => {
    const d = await apiFetch<{ portfolios: string[] }>('/api/portfolios');
    setPortfolios(d.portfolios);
    const fromUrl = searchParams.get('portfolio');
    const next =
      fromUrl && d.portfolios.includes(fromUrl)
        ? fromUrl
        : d.portfolios.includes(name)
          ? name
          : d.portfolios[0] ?? '';
    setName(next);
  }, [name, searchParams]);

  useEffect(() => {
    loadList()
      .catch(() => toast.error(t('portfolio.loadError')))
      .finally(() => setLoadingList(false));
  }, [loadList, t]);

  const loadPositions = useCallback(async () => {
    if (!name) return;
    const [stockRows, tradeRows, riskRow] = await Promise.all([
      apiFetch<{ stocks: PortfolioStock[] }>(`/api/portfolios/${encodeURIComponent(name)}/stocks`),
      apiFetch<{ transactions: PortfolioTransaction[] }>(
        `/api/portfolios/${encodeURIComponent(name)}/transactions?limit=50`,
      ),
      apiFetch<Record<string, number | boolean>>(`/api/portfolios/${encodeURIComponent(name)}/risk-control`),
    ]);
    setStocks(stockRows.stocks);
    setTrades(tradeRows.transactions);
    setRisk(riskRow);
    setRiskDraft(
      Object.fromEntries(Object.entries(riskRow).map(([key, value]) => [key, String(value)])),
    );
  }, [name]);

  useEffect(() => {
    if (ctxPortfolio && ctxPortfolio !== name) setName(ctxPortfolio);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ctxPortfolio]);

  useEffect(() => {
    if (name && name !== ctxPortfolio) setCtxPortfolio(name);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [name]);

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
    {
      key: 'run',
      label: t('portfolio.colRun'),
      render: (row) =>
        row.simulation_run_id ? (
          <Link to={`/simulation/results?run_id=${encodeURIComponent(row.simulation_run_id)}`}>
            {row.simulation_run_id.slice(0, 8)}
          </Link>
        ) : (
          '—'
        ),
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
          <div className="form-row" style={{ maxWidth: 280, marginBottom: 'var(--space-4)' }}>
            <label htmlFor="portfolio-config-select">{t('portfolio.select')}</label>
            <select id="portfolio-config-select" value={name} onChange={(e) => setName(e.target.value)}>
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
                              <span
                                className="portfolio-weight-fill"
                                style={{ width: `${(((s.market_value ?? 0) / totalMarketValue) * 100).toFixed(1)}%` }}
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
                                  style={{ left: `${fillLeft}%`, width: `${fillWidth}%` }}
                                />
                                <span
                                  className="portfolio-bullet-mark portfolio-bullet-mark--cost"
                                  style={{ left: `${pos(cost)}%` }}
                                />
                                {stop != null && (
                                  <span
                                    className="portfolio-bullet-mark portfolio-bullet-mark--stop"
                                    style={{ left: `${pos(stop)}%` }}
                                  />
                                )}
                                <span
                                  className="portfolio-bullet-mark portfolio-bullet-mark--price"
                                  style={{ left: `${pos(price)}%` }}
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
              <DataTable
                columns={holdingColumns}
                rows={stocks.filter((row) => row.status === statusFilter)}
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

              {tab === 'trades' && (
                <>
              <h2 className="portfolio-panel-title">{t('portfolio.tradesTitle')}</h2>
              <p className="portfolio-panel-desc">{t('portfolio.tradesDesc')}</p>
              <DataTable
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
