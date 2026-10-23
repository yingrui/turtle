import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { apiFetch } from '../../utils/api';
import { LineChart } from '../Chart';

type ChartData = { dates: string[]; series: { name: string; data: (number | null)[] }[] };

type Props = { tsCode: string };

/** ARIMA forecast for one symbol — the 预测 tab on the stock page. */
export function ForecastPanel({ tsCode }: Props) {
  const { t } = useTranslation();
  const [steps, setSteps] = useState(10);
  const [running, setRunning] = useState(false);
  const [chart, setChart] = useState<ChartData | null>(null);
  const [summary, setSummary] = useState('');

  async function run() {
    setRunning(true);
    try {
      const res = await apiFetch<{
        history: ChartData;
        forecast: { values: number[] };
        summary: string;
      }>(`/api/stocks/${encodeURIComponent(tsCode)}/forecast`, {
        method: 'POST',
        body: JSON.stringify({ steps }),
      });
      const last = res.history.series[0]?.data ?? [];
      setChart({
        dates: [...res.history.dates, ...res.forecast.values.map((_, i) => `F+${i + 1}`)],
        series: [
          ...res.history.series,
          {
            name: t('stockDetail.forecast.series'),
            data: [...Array(Math.max(0, last.length - 1)).fill(null), last[last.length - 1], ...res.forecast.values],
          },
        ],
      });
      setSummary(res.summary ?? '');
    } catch {
      setChart(null);
      setSummary('');
    } finally {
      setRunning(false);
    }
  }

  return (
    <>
      <div className="stock-detail-inline-form">
        <div className="form-row">
          <label htmlFor="forecast-steps">{t('stockDetail.forecast.steps')}</label>
          <input
            id="forecast-steps"
            type="number"
            min={5}
            max={30}
            value={steps}
            onChange={(e) => setSteps(Number(e.target.value))}
          />
        </div>
        <button type="button" className="btn btn-primary" onClick={run} disabled={running}>
          {running ? t('stockDetail.forecast.running') : t('stockDetail.forecast.run')}
        </button>
      </div>
      {chart && (
        <div className="chart-container">
          <LineChart data={chart} title={`${tsCode} · ${t('stockDetail.tab.forecast')}`} />
        </div>
      )}
      {summary && <pre className="log-panel stock-detail-forecast-summary">{summary.slice(0, 2000)}</pre>}
      {!chart && !running && <p className="stock-detail-hint">{t('stockDetail.forecast.hint')}</p>}
    </>
  );
}
