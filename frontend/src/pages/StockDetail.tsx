import { useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { toast } from 'sonner';
import { apiFetch } from '../utils/api';
import { CandlestickChart, LineChart, type OhlcvData } from '../components/Chart';
import './StockDetail.scss';

type Quote = {
  trade_date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  pre_close?: number;
  pct_chg: number;
  vol: number;
  amount: number;
};

type Snapshot = {
  ts_code: string;
  name: string;
  industry: string;
  market: string;
  exchange: string;
  quote: Quote | null;
};

const INDICATOR_TYPES = [
  { id: 'ma', labelKey: 'stockDetail.indicator.ma' },
  { id: 'donchian', labelKey: 'stockDetail.indicator.donchian' },
  { id: 'atr', labelKey: 'stockDetail.indicator.atr' },
  { id: 'bolling', labelKey: 'stockDetail.indicator.bolling' },
];

function formatAmount(v: number | undefined) {
  if (v == null) return '—';
  if (v >= 100000) return `${(v / 100000).toFixed(2)}亿`;
  if (v >= 10) return `${(v / 10).toFixed(1)}万`;
  return v.toFixed(0);
}

function formatVol(v: number | undefined) {
  if (v == null) return '—';
  if (v >= 10000) return `${(v / 10000).toFixed(1)}万`;
  return v.toFixed(0);
}

export function StockDetail() {
  const { t } = useTranslation();
  const { tsCode = '' } = useParams();
  const navigate = useNavigate();

  const [snapshot, setSnapshot] = useState<Snapshot | null>(null);
  const [ohlcv, setOhlcv] = useState<OhlcvData | null>(null);
  const [tab, setTab] = useState<'kline' | 'indicator'>('kline');
  const [indicatorType, setIndicatorType] = useState('ma');
  const [indicatorChart, setIndicatorChart] = useState<{
    dates: string[];
    series: { name: string; data: (number | null)[] }[];
  } | null>(null);
  const [portfolios, setPortfolios] = useState<string[]>([]);
  const [watchlistOpen, setWatchlistOpen] = useState(false);

  useEffect(() => {
    if (!tsCode) return;
    apiFetch<Snapshot>(`/api/stocks/${encodeURIComponent(tsCode)}/snapshot`)
      .then(setSnapshot)
      .catch(() => setSnapshot(null));
    apiFetch<OhlcvData>(`/api/stocks/${encodeURIComponent(tsCode)}/ohlcv?limit=250`)
      .then(setOhlcv)
      .catch(() => setOhlcv(null));
    apiFetch<{ portfolios: string[] }>('/api/portfolios')
      .then((d) => setPortfolios(d.portfolios))
      .catch(() => {});
  }, [tsCode]);

  useEffect(() => {
    if (!tsCode || tab !== 'indicator') return;
    apiFetch<{ dates: string[]; series: { name: string; data: (number | null)[] }[] }>(
      `/api/stocks/${encodeURIComponent(tsCode)}/indicators?chart=${indicatorType}`,
    ).then(setIndicatorChart);
  }, [tsCode, tab, indicatorType]);

  async function addWatchlist(portfolioName: string) {
    try {
      await apiFetch(`/api/portfolios/${encodeURIComponent(portfolioName)}/watchlist`, {
        method: 'POST',
        body: JSON.stringify({ ts_code: tsCode }),
      });
      toast.success(t('quote.addedToWatchlist', { code: tsCode, portfolio: portfolioName }));
      setWatchlistOpen(false);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed');
    }
  }

  const q = snapshot?.quote;
  const pctClass = q?.pct_chg != null ? (q.pct_chg > 0 ? 'up' : q.pct_chg < 0 ? 'down' : '') : '';

  return (
    <div className="page-card stock-detail">
      <p className="stock-detail-breadcrumb">
        <Link to="/market">{t('quote.backToQuotes')}</Link>
      </p>

      {snapshot ? (
        <header className="stock-detail-header">
          <div>
            <h1 className="page-title stock-detail-title">
              {snapshot.name}
              <span className="stock-detail-code">{snapshot.ts_code}</span>
            </h1>
            <p className="stock-detail-meta">
              {snapshot.industry ?? '—'} · {snapshot.market ?? snapshot.exchange}
              {q?.trade_date && (
                <span className="stock-detail-delayed"> · {t('quote.delayedData', { date: q.trade_date })}</span>
              )}
            </p>
          </div>
          <div className="stock-detail-actions">
            <button type="button" className="btn btn-secondary" onClick={() => navigate(`/forecast?ts_code=${encodeURIComponent(tsCode)}`)}>
              {t('nav.forecast')}
            </button>
            {portfolios.length > 0 && (
              <button type="button" className="btn btn-secondary" onClick={() => setWatchlistOpen((v) => !v)}>
                {t('quote.watchlist')}
              </button>
            )}
          </div>
        </header>
      ) : (
        <h1 className="page-title">{tsCode}</h1>
      )}

      {watchlistOpen && portfolios.length > 0 && (
        <div className="stock-detail-watchlist-pick">
          {portfolios.map((p) => (
            <button key={p} type="button" className="btn btn-sm" onClick={() => addWatchlist(p)}>
              {p}
            </button>
          ))}
        </div>
      )}

      {q && (
        <div className="stock-detail-quote-bar">
          <div className={`stock-detail-price ${pctClass}`}>{q.close.toFixed(2)}</div>
          <div className={`stock-detail-pct ${pctClass}`}>
            {q.pct_chg > 0 ? '+' : ''}
            {q.pct_chg.toFixed(2)}%
          </div>
          <dl className="stock-detail-stats">
            <div><dt>{t('quote.col.open')}</dt><dd>{q.open?.toFixed(2) ?? '—'}</dd></div>
            <div><dt>{t('quote.col.high')}</dt><dd>{q.high?.toFixed(2) ?? '—'}</dd></div>
            <div><dt>{t('quote.col.low')}</dt><dd>{q.low?.toFixed(2) ?? '—'}</dd></div>
            <div><dt>{t('quote.col.vol')}</dt><dd>{formatVol(q.vol)}</dd></div>
            <div><dt>{t('quote.col.amount')}</dt><dd>{formatAmount(q.amount)}</dd></div>
          </dl>
        </div>
      )}

      <div className="stock-detail-tabs">
        <button
          type="button"
          className={`stock-detail-tab${tab === 'kline' ? ' stock-detail-tab--active' : ''}`}
          onClick={() => setTab('kline')}
        >
          {t('stockDetail.tab.kline')}
        </button>
        <button
          type="button"
          className={`stock-detail-tab${tab === 'indicator' ? ' stock-detail-tab--active' : ''}`}
          onClick={() => setTab('indicator')}
        >
          {t('stockDetail.tab.indicator')}
        </button>
      </div>

      {tab === 'kline' && ohlcv && ohlcv.dates.length > 0 && (
        <div className="chart-container">
          <CandlestickChart data={ohlcv} />
        </div>
      )}
      {tab === 'kline' && (!ohlcv || ohlcv.dates.length === 0) && (
        <p style={{ color: 'var(--color-text-muted)' }}>{t('stockDetail.noChartData')}</p>
      )}

      {tab === 'indicator' && (
        <>
          <div className="form-row" style={{ maxWidth: 220, marginBottom: 'var(--space-4)' }}>
            <label>{t('stockDetail.indicator.label')}</label>
            <select value={indicatorType} onChange={(e) => setIndicatorType(e.target.value)}>
              {INDICATOR_TYPES.map((c) => (
                <option key={c.id} value={c.id}>{t(c.labelKey)}</option>
              ))}
            </select>
          </div>
          {indicatorChart && (
            <div className="chart-container">
              <LineChart data={indicatorChart} title={tsCode} />
            </div>
          )}
        </>
      )}
    </div>
  );
}
