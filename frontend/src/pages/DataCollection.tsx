import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { toast } from 'sonner';
import { apiFetch } from '../utils/api';
import { useJobPoll } from '../hooks/useJobPoll';

export function DataCollection() {
  const { t } = useTranslation();
  const [latestDate, setLatestDate] = useState('');
  const [fromDate, setFromDate] = useState('');
  const [toDate, setToDate] = useState('');
  const [tradeData, setTradeData] = useState(true);
  const [adjData, setAdjData] = useState(true);
  const [dividend, setDividend] = useState(true);
  const [calStartYear, setCalStartYear] = useState(new Date().getFullYear());
  const [jobId, setJobId] = useState<string | null>(null);
  const job = useJobPoll(jobId);

  useEffect(() => {
    apiFetch<{ latest_date: string }>('/api/data/latest-date')
      .then((d) => {
        setLatestDate(d.latest_date);
        setFromDate(d.latest_date);
        setToDate(d.latest_date);
      })
      .catch(() => toast.error('Failed to load latest date'));
  }, []);

  async function startJob(body: Record<string, unknown>) {
    try {
      const res = await apiFetch<{ id: string }>('/api/jobs', {
        method: 'POST',
        body: JSON.stringify(body),
      });
      setJobId(res.id);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to start job');
    }
  }

  return (
    <div className="page-card">
      <h1 className="page-title">{t('nav.data')}</h1>
      <p style={{ color: 'var(--color-text-muted)' }}>Latest data in database: {latestDate || '—'}</p>

      <h2 style={{ fontSize: 'var(--text-lg)', margin: 'var(--space-6) 0 var(--space-3)' }}>Market data sync</h2>
      <div style={{ display: 'flex', gap: 'var(--space-4)', flexWrap: 'wrap' }}>
        <div className="form-row" style={{ maxWidth: 200 }}>
          <label htmlFor="from-date">From</label>
          <input id="from-date" type="date" value={fromDate} onChange={(e) => setFromDate(e.target.value)} />
        </div>
        <div className="form-row" style={{ maxWidth: 200 }}>
          <label htmlFor="to-date">To</label>
          <input id="to-date" type="date" value={toDate} onChange={(e) => setToDate(e.target.value)} />
        </div>
      </div>
      <div className="policy-checkboxes">
        <label><input type="checkbox" checked={tradeData} onChange={(e) => setTradeData(e.target.checked)} /> OHLCV</label>
        <label><input type="checkbox" checked={adjData} onChange={(e) => setAdjData(e.target.checked)} /> Adj factors</label>
        <label><input type="checkbox" checked={dividend} onChange={(e) => setDividend(e.target.checked)} /> Dividends</label>
      </div>
      <button
        type="button"
        className="btn btn-primary"
        disabled={!fromDate}
        onClick={() =>
          startJob({ type: 'data_sync', from_date: fromDate, to_date: toDate, trade_data: tradeData, adj_data: adjData, dividend })
        }
      >
        Sync market data
      </button>

      <h2 style={{ fontSize: 'var(--text-lg)', margin: 'var(--space-6) 0 var(--space-3)' }}>Trade calendar</h2>
      <div className="form-row" style={{ maxWidth: 160 }}>
        <label>Year</label>
        <input type="number" value={calStartYear} onChange={(e) => setCalStartYear(Number(e.target.value))} />
      </div>
      <button
        type="button"
        className="btn btn-secondary"
        style={{ marginTop: 'var(--space-2)' }}
        onClick={() => startJob({ type: 'calendar_sync', start_year: calStartYear, end_year: calStartYear })}
      >
        Sync trade calendar (SSE/SZSE)
      </button>

      {job && (
        <div style={{ marginTop: 'var(--space-6)' }}>
          <p>Status: <strong>{job.status}</strong></p>
          {job.error && <p className="error-banner">{job.error}</p>}
          {job.log && <pre className="log-panel">{job.log}</pre>}
        </div>
      )}
    </div>
  );
}
