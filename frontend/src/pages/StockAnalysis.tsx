import { useEffect, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { apiFetch } from '../utils/api';
import { LineChart } from '../components/Chart';

type Stock = { ts_code: string; name: string };

const CHART_TYPES = [
  { id: 'ma', label: 'Moving Average' },
  { id: 'donchian', label: 'Donchian' },
  { id: 'atr', label: 'ATR' },
  { id: 'bolling', label: 'Bollinger' },
  { id: 'distribution', label: 'Returns Distribution' },
];

export function StockAnalysis() {
  const { t } = useTranslation();
  const [searchParams] = useSearchParams();
  const urlTsCode = searchParams.get('ts_code') ?? '';

  const [portfolios, setPortfolios] = useState<string[]>([]);
  const [portfolio, setPortfolio] = useState('');
  const [stocks, setStocks] = useState<Stock[]>([]);
  const [tsCode, setTsCode] = useState(urlTsCode);
  const [searchQ, setSearchQ] = useState('');
  const [searchHits, setSearchHits] = useState<Stock[]>([]);
  const [chartType, setChartType] = useState('ma');
  const [chart, setChart] = useState<{ dates: string[]; series: { name: string; data: (number | null)[] }[] } | null>(
    null,
  );

  useEffect(() => {
    if (urlTsCode) setTsCode(urlTsCode);
  }, [urlTsCode]);

  useEffect(() => {
    apiFetch<{ portfolios: string[] }>('/api/portfolios').then((d) => {
      setPortfolios(d.portfolios);
      if (d.portfolios.length) setPortfolio(d.portfolios[0]);
    });
  }, []);

  useEffect(() => {
    if (!portfolio) return;
    apiFetch<{ stocks: Stock[] }>(`/api/stocks?portfolio=${encodeURIComponent(portfolio)}`).then((d) => {
      setStocks(d.stocks);
      if (!urlTsCode && d.stocks.length) setTsCode(d.stocks[0].ts_code);
    });
  }, [portfolio, urlTsCode]);

  useEffect(() => {
    if (!searchQ.trim()) {
      setSearchHits([]);
      return;
    }
    const tmr = setTimeout(() => {
      apiFetch<{ stocks: Stock[] }>(`/api/stocks/search?q=${encodeURIComponent(searchQ.trim())}`)
        .then((d) => setSearchHits(d.stocks))
        .catch(() => setSearchHits([]));
    }, 300);
    return () => clearTimeout(tmr);
  }, [searchQ]);

  useEffect(() => {
    if (!tsCode) return;
    apiFetch<{ dates: string[]; series: { name: string; data: (number | null)[] }[] }>(
      `/api/stocks/${encodeURIComponent(tsCode)}/indicators?chart=${chartType}`,
    ).then(setChart);
  }, [tsCode, chartType]);

  const selectOptions = stocks.length ? stocks : searchHits;

  return (
    <div className="page-card">
      <p style={{ marginBottom: 'var(--space-4)' }}>
        <Link to="/market">{t('quote.backToQuotes')}</Link>
        {tsCode && (
          <>
            {' · '}
            <Link to={`/stocks/${encodeURIComponent(tsCode)}`}>{t('stockDetail.tab.kline')}</Link>
          </>
        )}
      </p>
      <h1 className="page-title">{t('nav.stocks')}</h1>
      <div style={{ display: 'flex', gap: 'var(--space-4)', flexWrap: 'wrap' }}>
        <div className="form-row" style={{ maxWidth: 200 }}>
          <label>Portfolio</label>
          <select value={portfolio} onChange={(e) => setPortfolio(e.target.value)}>
            {portfolios.map((p) => (
              <option key={p} value={p}>{p}</option>
            ))}
          </select>
        </div>
        <div className="form-row" style={{ maxWidth: 200 }}>
          <label>{t('quote.search')}</label>
          <input
            value={searchQ}
            onChange={(e) => setSearchQ(e.target.value)}
            placeholder={t('quote.searchPlaceholder')}
          />
        </div>
        <div className="form-row" style={{ maxWidth: 280 }}>
          <label>Stock</label>
          <select value={tsCode} onChange={(e) => setTsCode(e.target.value)}>
            {selectOptions.map((s) => (
              <option key={s.ts_code} value={s.ts_code}>{s.ts_code} — {s.name}</option>
            ))}
          </select>
        </div>
        <div className="form-row" style={{ maxWidth: 200 }}>
          <label>Chart</label>
          <select value={chartType} onChange={(e) => setChartType(e.target.value)}>
            {CHART_TYPES.map((c) => (
              <option key={c.id} value={c.id}>{c.label}</option>
            ))}
          </select>
        </div>
      </div>
      {chart && (
        <div className="chart-container">
          <LineChart data={chart} title={tsCode} />
        </div>
      )}
    </div>
  );
}
