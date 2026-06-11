import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { toast } from 'sonner';
import { apiFetch } from '../utils/api';
import { useJobPoll } from '../hooks/useJobPoll';

type ScreenRow = {
  ts_code: string;
  industry?: string;
  trend?: string;
  adf?: number;
  gradient?: number;
};

export function Screening() {
  const { t } = useTranslation();
  const [asOfDate, setAsOfDate] = useState(new Date().toISOString().slice(0, 10));
  const [trendFilter, setTrendFilter] = useState('');
  const [jobId, setJobId] = useState<string | null>(null);
  const [rows, setRows] = useState<ScreenRow[]>([]);
  const job = useJobPoll(jobId);

  useEffect(() => {
    if (job?.status !== 'completed' || !job.result) return;
    try {
      const parsed = JSON.parse(job.result) as { stocks: ScreenRow[] };
      setRows(parsed.stocks ?? []);
    } catch {
      setRows([]);
    }
  }, [job?.status, job?.result]);

  async function onScreen() {
    try {
      const res = await apiFetch<{ id: string }>('/api/jobs', {
        method: 'POST',
        body: JSON.stringify({
          type: 'portfolio_screen',
          as_of_date: asOfDate,
          ignore_st: true,
          trend_filter: trendFilter || undefined,
        }),
      });
      setJobId(res.id);
      setRows([]);
      toast.success('Screening started');
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to start screening');
    }
  }

  return (
    <div className="page-card">
      <h1 className="page-title">{t('nav.screening')}</h1>
      <p style={{ color: 'var(--color-text-muted)', marginBottom: 'var(--space-4)' }}>
        Universe screening: trend + ADF stationarity across listed stocks (PortfolioFilter).
      </p>
      <div style={{ display: 'flex', gap: 'var(--space-4)', flexWrap: 'wrap', alignItems: 'flex-end' }}>
        <div className="form-row" style={{ maxWidth: 200 }}>
          <label>As-of date</label>
          <input type="date" value={asOfDate} onChange={(e) => setAsOfDate(e.target.value)} />
        </div>
        <div className="form-row" style={{ maxWidth: 200 }}>
          <label>Trend filter</label>
          <select value={trendFilter} onChange={(e) => setTrendFilter(e.target.value)}>
            <option value="">All</option>
            <option value="up">Up</option>
            <option value="down">Down</option>
          </select>
        </div>
        <button type="button" className="btn btn-primary" onClick={onScreen}>
          Run screening
        </button>
      </div>
      {job && <p style={{ marginTop: 'var(--space-4)' }}>Status: <strong>{job.status}</strong></p>}
      {job?.error && <p className="error-banner">{job.error}</p>}
      {rows.length > 0 && (
        <table className="data-table">
          <thead>
            <tr>
              <th>Code</th>
              <th>Industry</th>
              <th>Trend</th>
              <th>ADF p</th>
              <th>Gradient</th>
            </tr>
          </thead>
          <tbody>
            {rows.slice(0, 100).map((row, i) => (
              <tr key={i}>
                <td>{row.ts_code}</td>
                <td>{row.industry ?? ''}</td>
                <td>{row.trend ?? ''}</td>
                <td>{row.adf != null ? Number(row.adf).toFixed(4) : ''}</td>
                <td>{row.gradient != null ? Number(row.gradient).toFixed(4) : ''}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
