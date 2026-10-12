import { useCallback, useEffect, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { toast } from 'sonner';
import { apiFetch } from '../utils/api';
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
  stop_loss_point: number | null;
  target_amount: number | null;
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

export function Portfolio() {
  const { t } = useTranslation();
  const [searchParams] = useSearchParams();
  const [portfolios, setPortfolios] = useState<string[]>([]);
  const [name, setName] = useState(searchParams.get('portfolio') ?? '');
  const [yaml, setYaml] = useState('');
  const [summary, setSummary] = useState<PortfolioConfig | null>(null);
  const [stocks, setStocks] = useState<PortfolioStock[]>([]);
  const [trades, setTrades] = useState<PortfolioTransaction[]>([]);
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

  useEffect(() => {
    if (!name) {
      setYaml('');
      setSummary(null);
      setStocks([]);
      setTrades([]);
      return;
    }
    apiFetch<{ yaml: string }>(`/api/portfolios/${encodeURIComponent(name)}/yaml`)
      .then((d) => setYaml(d.yaml))
      .catch(() => toast.error(t('portfolio.loadError')));
    apiFetch<PortfolioConfig>(`/api/portfolios/${encodeURIComponent(name)}`)
      .then(setSummary)
      .catch(() => setSummary(null));
    apiFetch<{ stocks: PortfolioStock[] }>(`/api/portfolios/${encodeURIComponent(name)}/stocks`)
      .then((d) => setStocks(d.stocks))
      .catch(() => setStocks([]));
    apiFetch<{ transactions: PortfolioTransaction[] }>(
      `/api/portfolios/${encodeURIComponent(name)}/transactions?limit=50`,
    )
      .then((d) => setTrades(d.transactions))
      .catch(() => setTrades([]));
  }, [name, t]);

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
              <div className="stat-grid">
                <div className="stat-card">
                  <span>{t('portfolio.statStocks')}</span>
                  <strong>{summary.follow_stocks?.length ?? 0}</strong>
                </div>
                <div className="stat-card">
                  <span>{t('portfolio.statPolicies')}</span>
                  <strong>{summary.policies?.length ?? 0}</strong>
                </div>
                <div className="stat-card">
                  <span>{t('portfolio.statCapital')}</span>
                  <strong>{summary.initial_investment?.toLocaleString() ?? '—'}</strong>
                </div>
              </div>

              <h2 className="portfolio-panel-title">{t('portfolio.holdingsTitle')}</h2>
              <p className="portfolio-panel-desc">{t('portfolio.holdingsDesc')}</p>
              {stocks.length === 0 ? (
                <p className="portfolio-muted">{t('portfolio.emptyHoldings')}</p>
              ) : (
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>{t('quote.col.ts_code')}</th>
                      <th>{t('portfolio.colStatus')}</th>
                      <th className="num">{t('portfolio.colShares')}</th>
                      <th className="num">{t('portfolio.colAvgCost')}</th>
                      <th className="num">{t('portfolio.colTotalCost')}</th>
                      <th className="num">{t('portfolio.colRealized')}</th>
                      <th className="num">{t('portfolio.colHolding')}</th>
                      <th className="num">{t('portfolio.colStopLoss')}</th>
                      <th className="num">{t('portfolio.colTarget')}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {stocks.map((s) => (
                      <tr key={s.ts_code}>
                        <td>{s.ts_code}</td>
                        <td>{statusLabel[s.status] ?? s.status}</td>
                        <td className="num">{s.hold_shares}</td>
                        <td className="num">{money(s.avg_cost)}</td>
                        <td className="num">{money(s.total_cost)}</td>
                        <td className={s.realized_pnl < 0 ? 'num down' : 'num up'}>{money(s.realized_pnl)}</td>
                        <td className="num">{s.holding_days ?? '—'}</td>
                        <td className="num">{money(s.stop_loss_point)}</td>
                        <td className="num">{money(s.target_amount)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}

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
                        <td className={(row.realized_pnl ?? 0) < 0 ? 'num down' : 'num up'}>
                          {money(row.realized_pnl)}
                        </td>
                        <td>{sourceLabel[row.source] ?? row.source}</td>
                        <td>{row.simulation_run_id ? row.simulation_run_id.slice(0, 8) : '—'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}

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
            </section>
          )}
        </>
      )}
    </div>
  );
}
