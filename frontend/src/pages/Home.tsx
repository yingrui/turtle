import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { apiFetch } from '../utils/api';
import { TodayTodo } from '../components/home/TodayTodo';
import './Home.scss';

type DataStatus = {
  as_of_date: string | null;
  tables: { name: string; latest_trade_date: string | null }[];
};

type UniverseMeta = {
  latest_trade_date: string | null;
  listed_count: number;
};

type IndustryItem = {
  industry: string;
  stock_count: number;
  avg_pct_chg: number | null;
};

type WatchlistItem = {
  ts_code: string;
  name?: string;
  quote: { close: number; pct_chg: number } | null;
};

function pctClass(v: number | null | undefined) {
  if (v == null) return '';
  if (v > 0) return 'price-up';
  if (v < 0) return 'price-down';
  return '';
}

function formatPct(v: number | null | undefined) {
  if (v == null) return '—';
  return `${v > 0 ? '+' : ''}${v.toFixed(2)}%`;
}

export function Home() {
  const { t } = useTranslation();
  const [loading, setLoading] = useState(true);
  const [dataStatus, setDataStatus] = useState<DataStatus | null>(null);
  const [meta, setMeta] = useState<UniverseMeta | null>(null);
  const [industries, setIndustries] = useState<IndustryItem[]>([]);
  const [portfolio, setPortfolio] = useState<string | null>(null);
  const [watchlist, setWatchlist] = useState<WatchlistItem[]>([]);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const [statusRes, metaRes, industryRes, portfoliosRes] = await Promise.all([
          apiFetch<DataStatus>('/api/data/status'),
          apiFetch<UniverseMeta>('/api/stocks/universe/meta'),
          apiFetch<{ items: IndustryItem[] }>('/api/stocks/universe/industry-summary?limit=12'),
          apiFetch<{ portfolios: string[] }>('/api/portfolios'),
        ]);

        if (cancelled) return;

        setDataStatus(statusRes);
        setMeta(metaRes);
        setIndustries(industryRes.items ?? []);

        const firstPortfolio = portfoliosRes.portfolios[0] ?? null;
        setPortfolio(firstPortfolio);

        if (firstPortfolio) {
          const wl = await apiFetch<{ items: WatchlistItem[] }>(
            `/api/portfolios/${encodeURIComponent(firstPortfolio)}/watchlist`,
          );
          if (!cancelled) {
            const all = wl.items ?? [];
            const sorted = [...all].sort(
              (a, b) => Math.abs(b.quote?.pct_chg ?? 0) - Math.abs(a.quote?.pct_chg ?? 0),
            );
            setWatchlist(sorted.slice(0, 8));
          }
        } else {
          setWatchlist([]);
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    load();
    return () => {
      cancelled = true;
    };
  }, []);

  const marketDate = meta?.latest_trade_date ?? dataStatus?.as_of_date;
  const industryLeaders = industries.slice(0, 5);
  const industryLaggards = [...industries].reverse().slice(0, 5);

  return (
    <div className="page-card home-dashboard">
      <header className="home-header">
        <h1 className="page-title">{t('home.dashboardTitle')}</h1>
        <p className="home-subtitle">{t('home.dashboardSubtitle')}</p>
      </header>

      {loading ? (
        <p className="home-muted">{t('home.loading')}</p>
      ) : (
        <>
          <TodayTodo />

          <p className="home-muted home-asof">
            {t('home.marketLine', {
              date: marketDate ?? t('settings.unknown'),
              count: meta?.listed_count ?? 0,
            })}
          </p>

          <div className="home-grid">
            <section className="home-panel">
              <div className="home-panel-head">
                <h2>{t('home.watchlistSection')}</h2>
                <Link to={portfolio ? `/watchlist?portfolio=${encodeURIComponent(portfolio)}` : '/watchlist'}>
                  {t('home.viewAll')}
                </Link>
              </div>
              {!portfolio ? (
                <div className="home-empty">
                  <p>{t('home.noPortfolioHint')}</p>
                  <Link to="/watchlist" className="btn btn-primary btn-sm">
                    {t('watchlist.createPortfolio')}
                  </Link>
                </div>
              ) : watchlist.length === 0 ? (
                <div className="home-empty">
                  <p>{t('home.emptyWatchlist')}</p>
                  <Link to="/screening" className="btn btn-primary btn-sm">
                    {t('watchlist.goPick')}
                  </Link>
                </div>
              ) : (
                <table className="data-table home-table">
                  <thead>
                    <tr>
                      <th>{t('quote.col.ts_code')}</th>
                      <th>{t('quote.col.name')}</th>
                      <th>{t('quote.col.close')}</th>
                      <th>{t('quote.col.pct_chg')}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {watchlist.map((item) => (
                      <tr key={item.ts_code}>
                        <td>
                          <Link to={`/stocks/${encodeURIComponent(item.ts_code)}`}>{item.ts_code}</Link>
                        </td>
                        <td>{item.name ?? '—'}</td>
                        <td>{item.quote?.close != null ? item.quote.close.toFixed(2) : '—'}</td>
                        <td className={pctClass(item.quote?.pct_chg)}>
                          {formatPct(item.quote?.pct_chg)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </section>

            <section className="home-panel">
              <div className="home-panel-head">
                <h2>{t('home.industrySection')}</h2>
                <Link to="/market">{t('home.viewMarket')}</Link>
              </div>
              {industries.length === 0 ? (
                <p className="home-muted">{t('home.noIndustryData')}</p>
              ) : (
                <div className="home-industry-cols">
                  <div>
                    <h3>{t('home.industryLeaders')}</h3>
                    <ul className="home-industry-list">
                      {industryLeaders.map((item) => (
                        <li key={`up-${item.industry}`}>
                          <span>{item.industry}</span>
                          <span className={`home-industry-pct ${pctClass(item.avg_pct_chg)}`}>
                            {formatPct(item.avg_pct_chg)}
                          </span>
                        </li>
                      ))}
                    </ul>
                  </div>
                  <div>
                    <h3>{t('home.industryLaggards')}</h3>
                    <ul className="home-industry-list">
                      {industryLaggards.map((item) => (
                        <li key={`down-${item.industry}`}>
                          <span>{item.industry}</span>
                          <span className={`home-industry-pct ${pctClass(item.avg_pct_chg)}`}>
                            {formatPct(item.avg_pct_chg)}
                          </span>
                        </li>
                      ))}
                    </ul>
                  </div>
                </div>
              )}
            </section>
          </div>

          <div className="home-actions">
            <Link to="/watchlist" className="btn btn-primary">{t('nav.watchlist')}</Link>
            <Link to="/screening" className="btn btn-secondary">{t('nav.screening')}</Link>
            <Link to="/market" className="btn btn-secondary">{t('nav.quote')}</Link>
            <Link to="/simulation" className="btn btn-secondary">{t('nav.simulation')}</Link>
            <Link to="/data" className="btn btn-secondary">{t('nav.data')}</Link>
          </div>
        </>
      )}
    </div>
  );
}
