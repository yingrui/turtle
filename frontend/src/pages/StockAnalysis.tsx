import { useEffect, useState } from 'react';
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
  const [portfolios, setPortfolios] = useState<string[]>([]);
  const [portfolio, setPortfolio] = useState('');
  const [stocks, setStocks] = useState<Stock[]>([]);
  const [tsCode, setTsCode] = useState('');
  const [chartType, setChartType] = useState('ma');
  const [chart, setChart] = useState<{ dates: string[]; series: { name: string; data: (number | null)[] }[] } | null>(
    null,
  );

  useEffect(() => {
    apiFetch<{ portfolios: string[] }>('/api/portfolios').then((d) => {
      setPortfolios(d.portfolios);
      if (d.portfolios.length) setPortfolio(d.portfolios[0]);
    });
  }, []);

  useEffect(() => {
    if (!portfolio) return;
    apiFetch<{ stocks: Stock[] }>(`/api/stocks?portfolio=${portfolio}`).then((d) => {
      setStocks(d.stocks);
      if (d.stocks.length) setTsCode(d.stocks[0].ts_code);
    });
  }, [portfolio]);

  useEffect(() => {
    if (!tsCode) return;
    apiFetch<{ dates: string[]; series: { name: string; data: (number | null)[] }[] }>(
      `/api/stocks/${encodeURIComponent(tsCode)}/indicators?chart=${chartType}`,
    ).then(setChart);
  }, [tsCode, chartType]);

  return (
    <div className="page-card">
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
        <div className="form-row" style={{ maxWidth: 280 }}>
          <label>Stock</label>
          <select value={tsCode} onChange={(e) => setTsCode(e.target.value)}>
            {stocks.map((s) => (
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
