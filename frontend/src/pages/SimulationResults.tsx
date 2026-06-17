import { useEffect, useMemo, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { apiFetch } from '../utils/api';
import { LineChart } from '../components/Chart';
import { Tabs } from '../components/Tabs';

type Run = {
  id: string;
  job_id: string | null;
  portfolio_name: string;
  policy_id: number;
  started_at: string | null;
};

type Summary = {
  policy_id: number;
  initial_total: number;
  total: number;
  years: number;
  return_rate_pct: number;
  cagr: number;
};

type CompareRow = Summary & { id: string };

type JobRow = {
  id: string;
  type: string;
  status: string;
  created_at: string | null;
};

export function SimulationResults() {
  const { t } = useTranslation();
  const [searchParams, setSearchParams] = useSearchParams();
  const jobIdParam = searchParams.get('job_id');
  const runIdParam = searchParams.get('run_id');

  const [runs, setRuns] = useState<Run[]>([]);
  const [recentJobs, setRecentJobs] = useState<JobRow[]>([]);
  const [loadingRuns, setLoadingRuns] = useState(true);
  const [tab, setTab] = useState('chart');
  const [summary, setSummary] = useState<Summary | null>(null);
  const [chart, setChart] = useState<{ dates: string[]; series: { name: string; data: (number | null)[] }[] } | null>(null);
  const [trades, setTrades] = useState<Record<string, unknown>[]>([]);
  const [benefit, setBenefit] = useState<Record<string, unknown>[]>([]);
  const [winLoss, setWinLoss] = useState<{ win: number; loss: number; holding: number } | null>(null);
  const [compare, setCompare] = useState<CompareRow[]>([]);

  useEffect(() => {
    apiFetch<{ jobs: JobRow[] }>('/api/jobs')
      .then((d) => setRecentJobs((d.jobs ?? []).filter((j) => j.type === 'simulation')))
      .catch(() => setRecentJobs([]));
  }, []);

  useEffect(() => {
    setLoadingRuns(true);
    const q = jobIdParam ? `?job_id=${encodeURIComponent(jobIdParam)}` : '';
    apiFetch<{ runs: Run[] }>(`/api/simulations${q}`)
      .then((d) => setRuns(d.runs ?? []))
      .catch(() => setRuns([]))
      .finally(() => setLoadingRuns(false));

    if (jobIdParam) {
      apiFetch<{ policies: CompareRow[] }>(`/api/simulations/compare?job_id=${encodeURIComponent(jobIdParam)}`)
        .then((d) => setCompare(d.policies ?? []))
        .catch(() => setCompare([]));
    } else {
      setCompare([]);
    }
  }, [jobIdParam]);

  const selectedRunId = useMemo(() => {
    if (runIdParam && runs.some((r) => r.id === runIdParam)) return runIdParam;
    return runs[0]?.id ?? '';
  }, [runs, runIdParam]);

  useEffect(() => {
    if (!runs.length || !selectedRunId) return;
    if (runIdParam === selectedRunId) return;
    setSearchParams(
      (prev) => {
        const p = new URLSearchParams(prev);
        if (jobIdParam) p.set('job_id', jobIdParam);
        p.set('run_id', selectedRunId);
        return p;
      },
      { replace: true },
    );
  }, [runs, selectedRunId, runIdParam, jobIdParam, setSearchParams]);

  useEffect(() => {
    if (!selectedRunId) {
      setSummary(null);
      setChart(null);
      setTrades([]);
      setBenefit([]);
      setWinLoss(null);
      return;
    }
    apiFetch<Summary>(`/api/simulations/${selectedRunId}/summary`).then(setSummary).catch(() => setSummary(null));
    apiFetch<{ dates: string[]; series: { name: string; data: (number | null)[] }[] }>(
      `/api/simulations/${selectedRunId}/daily`,
    ).then(setChart);
    apiFetch<{ trades: Record<string, unknown>[] }>(`/api/simulations/${selectedRunId}/trades`).then((d) =>
      setTrades(d.trades),
    );
    apiFetch<{ benefit: Record<string, unknown>[] }>(`/api/simulations/${selectedRunId}/benefit`).then((d) =>
      setBenefit(d.benefit),
    );
    apiFetch<{ win: number; loss: number; holding: number }>(`/api/simulations/${selectedRunId}/win-loss`).then(
      setWinLoss,
    );
  }, [selectedRunId]);

  function selectJob(jobId: string) {
    if (!jobId) {
      setSearchParams({}, { replace: true });
      return;
    }
    setSearchParams({ job_id: jobId }, { replace: true });
  }

  function selectRun(runId: string) {
    setSearchParams(
      (prev) => {
        const p = new URLSearchParams(prev);
        if (jobIdParam) p.set('job_id', jobIdParam);
        p.set('run_id', runId);
        return p;
      },
      { replace: true },
    );
  }

  const run = runs.find((r) => r.id === selectedRunId);

  return (
    <>
      <p style={{ color: 'var(--color-text-muted)', marginBottom: 'var(--space-4)' }}>
        {t('results.subtitle')}
      </p>

      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 'var(--space-4)', marginBottom: 'var(--space-4)' }}>
        <div className="form-row" style={{ minWidth: 280, maxWidth: 420, margin: 0 }}>
          <label htmlFor="sim-job">{t('results.selectJob')}</label>
          <select id="sim-job" value={jobIdParam ?? ''} onChange={(e) => selectJob(e.target.value)}>
            <option value="">{t('results.allRecent')}</option>
            {recentJobs.map((j) => (
              <option key={j.id} value={j.id}>
                {j.created_at?.slice(0, 16).replace('T', ' ') ?? j.id} — {j.status}
              </option>
            ))}
          </select>
        </div>
        {runs.length > 0 && (
          <div className="form-row" style={{ minWidth: 280, maxWidth: 480, margin: 0 }}>
            <label htmlFor="sim-run">{t('results.selectRun')}</label>
            <select id="sim-run" value={selectedRunId} onChange={(e) => selectRun(e.target.value)}>
              {runs.map((r) => (
                <option key={r.id} value={r.id}>
                  {r.portfolio_name} — policy {r.policy_id} ({r.started_at?.slice(0, 10) ?? '—'})
                </option>
              ))}
            </select>
          </div>
        )}
      </div>

      {loadingRuns && <p style={{ color: 'var(--color-text-muted)' }}>{t('results.loading')}</p>}

      {!loadingRuns && runs.length === 0 && (
        <div style={{ padding: 'var(--space-4)', border: '1px dashed var(--color-border)', borderRadius: 'var(--radius-md)' }}>
          <p style={{ color: 'var(--color-text-muted)', margin: '0 0 var(--space-3)' }}>{t('results.empty')}</p>
          <Link to="/simulation" className="btn btn-primary btn-sm">{t('simulation.tabRun')}</Link>
        </div>
      )}

      {compare.length > 1 && (
        <div style={{ marginBottom: 'var(--space-6)' }}>
          <h2 style={{ fontSize: 'var(--text-lg)', marginBottom: 'var(--space-3)' }}>{t('results.compareTitle')}</h2>
          <table className="data-table">
            <thead>
              <tr>
                <th>{t('results.policy')}</th>
                <th>CAGR</th>
                <th>{t('results.returnPct')}</th>
                <th>{t('results.final')}</th>
              </tr>
            </thead>
            <tbody>
              {compare.map((row) => (
                <tr key={row.id}>
                  <td>{row.policy_id}</td>
                  <td>{row.cagr}</td>
                  <td>{row.return_rate_pct}</td>
                  <td>{row.total}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {summary && winLoss && (
        <div className="stat-grid">
          <div className="stat-card"><span>CAGR</span><strong>{summary.cagr}</strong></div>
          <div className="stat-card"><span>{t('results.returnPct')}</span><strong>{summary.return_rate_pct}%</strong></div>
          <div className="stat-card"><span>{t('results.wins')}</span><strong>{winLoss.win}</strong></div>
          <div className="stat-card"><span>{t('results.losses')}</span><strong>{winLoss.loss}</strong></div>
        </div>
      )}

      {selectedRunId && (
        <Tabs
          tabs={[
            { id: 'chart', label: t('results.tabChart') },
            { id: 'trades', label: t('results.tabTrades') },
            { id: 'benefit', label: t('results.tabBenefit') },
          ]}
          active={tab}
          onChange={setTab}
        >
          {tab === 'chart' && chart && (
            <div className="chart-container">
              <LineChart data={chart} title={run ? `Policy ${run.policy_id}` : undefined} />
            </div>
          )}
          {tab === 'trades' && trades.length > 0 && (
            <table className="data-table">
              <thead>
                <tr>
                  <th>{t('results.colDate')}</th>
                  <th>{t('quote.col.ts_code')}</th>
                  <th>{t('results.colStatus')}</th>
                  <th>{t('results.colBuy')}</th>
                  <th>{t('results.colSell')}</th>
                  <th>{t('results.colBenefit')}</th>
                  <th>{t('results.colReason')}</th>
                </tr>
              </thead>
              <tbody>
                {trades.slice(-80).map((row, i) => (
                  <tr key={i}>
                    <td>{String(row.date)}</td>
                    <td>{String(row.ts_code)}</td>
                    <td>{String(row.status)}</td>
                    <td>{String(row.buy_price ?? '')}</td>
                    <td>{String(row.sell_price ?? '')}</td>
                    <td>{String(row.benefit ?? '')}</td>
                    <td>{String(row.reason ?? '')}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          {tab === 'benefit' && benefit.length > 0 && (
            <table className="data-table">
              <thead>
                <tr>
                  <th>{t('quote.col.ts_code')}</th>
                  <th>{t('results.colBenefit')}</th>
                </tr>
              </thead>
              <tbody>
                {benefit
                  .filter((b) => b.ts_code)
                  .slice(0, 50)
                  .map((row, i) => (
                    <tr key={i}>
                      <td>{String(row.ts_code)}</td>
                      <td>{String(Object.values(row).find((v) => typeof v === 'number') ?? '')}</td>
                    </tr>
                  ))}
              </tbody>
            </table>
          )}
        </Tabs>
      )}
    </>
  );
}
