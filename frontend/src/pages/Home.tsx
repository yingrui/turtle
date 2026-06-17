import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { apiFetch } from '../utils/api';
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

type Job = {
  id: string;
  type: string;
  status: string;
  created_at: string | null;
};

const JOB_TYPES = new Set(['portfolio_screen', 'simulation']);

function pctClass(v: number | null | undefined) {
  if (v == null) return '';
  if (v > 0) return 'up';
  if (v < 0) return 'down';
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
  const [watchlistTotal, setWatchlistTotal] = useState(0);
  const [jobs, setJobs] = useState<Job[]>([]);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const [statusRes, metaRes, industryRes, portfoliosRes, jobsRes] = await Promise.all([
          apiFetch<DataStatus>('/api/data/status'),
          apiFetch<UniverseMeta>('/api/stocks/universe/meta'),
          apiFetch<{ items: IndustryItem[] }>('/api/stocks/universe/industry-summary?limit=12'),
          apiFetch<{ portfolios: string[] }>('/api/portfolios'),
          apiFetch<{ jobs: Job[] }>('/api/jobs'),
        ]);

        if (cancelled) return;

        setDataStatus(statusRes);
        setMeta(metaRes);
        setIndustries(industryRes.items ?? []);
        setJobs(
          (jobsRes.jobs ?? [])
            .filter((j) => JOB_TYPES.has(j.type))
            .slice(0, 6),
        );

        const firstPortfolio = portfoliosRes.portfolios[0] ?? null;
        setPortfolio(firstPortfolio);

        if (firstPortfolio) {
          const wl = await apiFetch<{ items: WatchlistItem[] }>(
            `/api/portfolios/${encodeURIComponent(firstPortfolio)}/watchlist`,
          );
          if (!cancelled) {
            const all = wl.items ?? [];
            setWatchlistTotal(all.length);
            const sorted = [...all].sort(
              (a, b) => Math.abs(b.quote?.pct_chg ?? 0) - Math.abs(a.quote?.pct_chg ?? 0),
            );
            setWatchlist(sorted.slice(0, 8));
          }
        } else {
          setWatchlist([]);
          setWatchlistTotal(0);
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

  const dailyBasicDate = dataStatus?.tables.find((tb) => tb.name === 'daily_basic')?.latest_trade_date;
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
          <div className="home-stats">
            <div className="stat-card">
              <span>{t('home.statMarket')}</span>
              <strong>{marketDate ?? '—'}</strong>
              <small>{t('home.listedCount', { count: meta?.listed_count ?? 0 })}</small>
            </div>
            <div className="stat-card">
              <span>{t('home.statDailyBasic')}</span>
              <strong>{dailyBasicDate ?? '—'}</strong>
              {!dailyBasicDate && (
                <small className="home-warn">{t('home.dailyBasicMissing')}</small>
              )}
            </div>
            <div className="stat-card">
              <span>{t('home.statPortfolio')}</span>
              <strong>{portfolio ?? t('home.noPortfolio')}</strong>
              <small>{t('home.watchlistCount', { count: watchlistTotal })}</small>
            </div>
          </div>

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

          <section className="home-panel home-jobs">
            <div className="home-panel-head">
              <h2>{t('home.jobsSection')}</h2>
              <Link to="/jobs">{t('home.viewAll')}</Link>
            </div>
            {jobs.length === 0 ? (
              <p className="home-muted">{t('home.noJobs')}</p>
            ) : (
              <table className="data-table home-table">
                <thead>
                  <tr>
                    <th>{t('home.jobType')}</th>
                    <th>{t('home.jobStatus')}</th>
                    <th>{t('home.jobTime')}</th>
                    <th>{t('quote.col.actions')}</th>
                  </tr>
                </thead>
                <tbody>
                  {jobs.map((job) => (
                    <tr key={job.id}>
                      <td>{job.type}</td>
                      <td>{job.status}</td>
                      <td>{job.created_at?.slice(0, 16).replace('T', ' ') ?? '—'}</td>
                      <td>
                        {job.type === 'simulation' && job.status === 'completed' && (
                          <Link to={`/simulation/results?job_id=${encodeURIComponent(job.id)}`}>
                            {t('simulation.viewResults')}
                          </Link>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </section>

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
