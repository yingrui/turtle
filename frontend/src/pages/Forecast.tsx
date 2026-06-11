import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { apiFetch } from '../utils/api';
import { LineChart } from '../components/Chart';

type Stock = { ts_code: string; name: string };

export function Forecast() {
  const { t } = useTranslation();
  const [portfolios, setPortfolios] = useState<string[]>([]);
  const [portfolio, setPortfolio] = useState('');
  const [stocks, setStocks] = useState<Stock[]>([]);
  const [tsCode, setTsCode] = useState('');
  const [history, setHistory] = useState<{ dates: string[]; series: { name: string; data: (number | null)[] }[] } | null>(
    null,
  );
  const [steps, setSteps] = useState(10);
  const [forecastValues, setForecastValues] = useState<number[]>([]);
  const [summary, setSummary] = useState('');

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

  async function onForecast() {
    if (!tsCode) return;
    const res = await apiFetch<{
      history: { dates: string[]; series: { name: string; data: (number | null)[] }[] };
      forecast: { values: number[] };
      summary: string;
    }>(`/api/stocks/${encodeURIComponent(tsCode)}/forecast`, {
      method: 'POST',
      body: JSON.stringify({ steps }),
    });
    setHistory(res.history);
    setForecastValues(res.forecast.values);
    setSummary(res.summary);
  }

  const chartData = history
    ? {
        dates: [
          ...history.dates,
          ...forecastValues.map((_, i) => `F+${i + 1}`),
        ],
        series: [
          ...history.series,
          {
            name: 'forecast',
            data: [
              ...Array(history.dates.length - 1).fill(null),
              history.series[0]?.data[history.series[0].data.length - 1],
              ...forecastValues,
            ],
          },
        ],
      }
    : null;

  return (
    <div className="page-card">
      <h1 className="page-title">{t('nav.forecast')}</h1>
      <div style={{ display: 'flex', gap: 'var(--space-4)', flexWrap: 'wrap', alignItems: 'flex-end' }}>
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
        <div className="form-row" style={{ maxWidth: 120 }}>
          <label>Steps</label>
          <input type="number" min={5} max={30} value={steps} onChange={(e) => setSteps(Number(e.target.value))} />
        </div>
        <button type="button" className="btn btn-primary" onClick={onForecast}>
          Run ARIMA Forecast
        </button>
      </div>
      {chartData && (
        <div className="chart-container">
          <LineChart data={chartData} title={`Forecast: ${tsCode}`} />
        </div>
      )}
      {summary && <pre className="log-panel" style={{ maxHeight: 200 }}>{summary.slice(0, 2000)}</pre>}
    </div>
  );
}
