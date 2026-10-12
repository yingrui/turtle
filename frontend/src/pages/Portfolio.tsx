import { useCallback, useEffect, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { toast } from 'sonner';
import { apiFetch } from '../utils/api';
import { TradeDrawer } from '../components/portfolio/TradeDrawer';
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
  const [searchParams] = useSearchParams();
  const [portfolios, setPortfolios] = useState<string[]>([]);
  const [name, setName] = useState(searchParams.get('portfolio') ?? '');
  const [yaml, setYaml] = useState('');
  const [summary, setSummary] = useState<PortfolioConfig | null>(null);
  const [stocks, setStocks] = useState<PortfolioStock[]>([]);
  const [trades, setTrades] = useState<PortfolioTransaction[]>([]);
  const [draft, setDraft] = useState<TradeDraft | null>(null);
  const [tab, setTab] = useState<'overview' | 'holdings' | 'trades' | 'risk' | 'advanced'>('overview');
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
              {stocks.length === 0 ? (
                <p className="portfolio-muted">
                  {t('portfolio.emptyHoldings')} <Link to="/screening">{t('portfolio.emptyHoldingsCta')}</Link>
                </p>
              ) : (
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>{t('quote.col.ts_code')}</th>
                      <th>{t('portfolio.colStatus')}</th>
                      <th className="num">{t('portfolio.colShares')}</th>
                      <th className="num">{t('portfolio.colAvgCost')}</th>
                      <th className="num">{t('portfolio.colLastPrice')}</th>
                      <th className="num">{t('portfolio.colMarketValue')}</th>
                      <th className="num">{t('portfolio.colUnrealized')}</th>
                      <th className="num">{t('portfolio.colTotalCost')}</th>
                      <th className="num">{t('portfolio.colRealized')}</th>
                      <th className="num">{t('portfolio.colHolding')}</th>
                      <th className="num">{t('portfolio.colStopLoss')}</th>
                      <th className="num">{t('portfolio.colTarget')}</th>
                      <th>{t('portfolio.colRisk')}</th>
                      <th>{t('portfolio.colActions')}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {stocks.map((s) => (
                      <tr key={s.ts_code}>
                        <td>
                          <Link to={`/stocks/${encodeURIComponent(s.ts_code)}`}>{s.ts_code}</Link>
                        </td>
                        <td>{statusLabel[s.status] ?? s.status}</td>
                        <td className="num">{s.hold_shares}</td>
                        <td className="num">{money(s.avg_cost)}</td>
                        <td className="num">{money(s.current_price)}</td>
                        <td className="num">{money(s.market_value)}</td>
                        <td className={(s.unrealized_pnl ?? 0) < 0 ? 'num price-down' : 'num price-up'}>
                          {money(s.unrealized_pnl)}
                          {s.unrealized_pct != null ? ` (${s.unrealized_pct}%)` : ''}
                        </td>
                        <td className="num">{money(s.total_cost)}</td>
                        <td className={s.realized_pnl < 0 ? 'num price-down' : 'num price-up'}>
                          {money(s.realized_pnl)}
                        </td>
                        <td className="num">{s.holding_days ?? '—'}</td>
                        <td className="num">
                          <input
                            className="portfolio-cell-input"
                            type="number"
                            step="0.01"
                            defaultValue={s.stop_loss_point ?? ''}
                            aria-label={t('portfolio.colStopLoss')}
                            onBlur={(e) => {
                              const raw = e.target.value.trim();
                              const next = raw === '' ? null : Number(raw);
                              if (next !== (s.stop_loss_point ?? null)) patchStock(s, { stop_loss_point: next });
                            }}
                          />
                        </td>
                        <td className="num">
                          <input
                            className="portfolio-cell-input"
                            type="number"
                            step="1"
                            defaultValue={s.target_amount ?? ''}
                            aria-label={t('portfolio.colTarget')}
                            onBlur={(e) => {
                              const raw = e.target.value.trim();
                              const next = raw === '' ? null : Number(raw);
                              if (next !== (s.target_amount ?? null)) patchStock(s, { target_amount: next });
                            }}
                          />
                        </td>
                        <td className="portfolio-risk-flags">
                          {riskFlags(s).map((f) => (
                            <span key={f.label} className={`portfolio-flag portfolio-flag--${f.level}`}>
                              {f.label}
                            </span>
                          ))}
                        </td>
                        <td className="portfolio-row-actions">
                          <button type="button" className="btn btn-sm" onClick={() => openTrade('buy', s)}>
                            {t('portfolio.actionBuy')}
                          </button>
                          <button
                            type="button"
                            className="btn btn-sm"
                            onClick={() => openTrade('sell', s)}
                            disabled={s.hold_shares <= 0}
                            title={s.hold_shares <= 0 ? t('portfolio.actionSellDisabled') : undefined}
                          >
                            {t('portfolio.actionSell')}
                          </button>
                          <button
                            type="button"
                            className="btn btn-sm btn-secondary"
                            onClick={() => removeStock(s)}
                            disabled={s.hold_shares > 0}
                            title={s.hold_shares > 0 ? t('portfolio.removeStockBlocked') : undefined}
                          >
                            {t('portfolio.actionRemove')}
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
                </>
              )}

              {tab === 'trades' && (
                <>
              <h2 className="portfolio-panel-title">{t('portfolio.tradesTitle')}</h2>
              <p className="portfolio-panel-desc">{t('portfolio.tradesDesc')}</p>
              {trades.length === 0 ? (
                <p className="portfolio-muted">{t('portfolio.emptyTrades')}</p>
              ) : (
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>{t('portfolio.colTradeDate')}</th>
                      <th>{t('quote.col.ts_code')}</th>
                      <th>{t('portfolio.colSide')}</th>
                      <th className="num">{t('portfolio.colShares')}</th>
                      <th className="num">{t('portfolio.colPrice')}</th>
                      <th className="num">{t('portfolio.colAmount')}</th>
                      <th className="num">{t('portfolio.colRealized')}</th>
                      <th>{t('portfolio.colSource')}</th>
                      <th>{t('portfolio.colRun')}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {trades.map((row) => (
                      <tr key={row.id}>
                        <td>{row.trade_date}</td>
                        <td>{row.ts_code}</td>
                        <td>{row.side === 'buy' ? t('portfolio.sideBuy') : t('portfolio.sideSell')}</td>
                        <td className="num">{row.shares}</td>
                        <td className="num">{money(row.price)}</td>
                        <td className="num">{money(row.amount)}</td>
                        <td className={(row.realized_pnl ?? 0) < 0 ? 'num price-down' : 'num price-up'}>
                          {money(row.realized_pnl)}
                        </td>
                        <td>{sourceLabel[row.source] ?? row.source}</td>
                        <td>
                          {row.simulation_run_id ? (
                            <Link to={`/simulation/results?run_id=${encodeURIComponent(row.simulation_run_id)}`}>
                              {row.simulation_run_id.slice(0, 8)}
                            </Link>
                          ) : (
                            '—'
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
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
                  {(summary.policies ?? []).length === 0 ? (
                    <p className="portfolio-muted">{t('portfolio.policiesEmpty')}</p>
                  ) : (
                    <table className="data-table">
                      <thead>
                        <tr>
                          <th>{t('portfolio.policyName')}</th>
                          <th>{t('portfolio.policyParams')}</th>
                        </tr>
                      </thead>
                      <tbody>
                        {(summary.policies as Record<string, unknown>[]).map((policy, i) => (
                          <tr key={i}>
                            <td>{String(policy['trade_policy.name'] ?? '—')}</td>
                            <td>
                              {Object.entries(policy)
                                .filter(([key]) => key !== 'trade_policy.name')
                                .map(([key, value]) => `${key.replace(/^trade_policy\.[^.]+\./, '')}=${String(value)}`)
                                .join('  ')}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  )}
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
