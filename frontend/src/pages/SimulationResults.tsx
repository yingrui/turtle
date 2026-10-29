import { useEffect, useMemo, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { apiFetch } from '../utils/api';
import { LineChart } from '../components/Chart';
import { Tabs } from '../components/Tabs';
import { DataTable, type Column } from '../components/DataTable';

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

type Benchmark = {
  ts_code: string;
  dates: string[];
  equity: number[];
  benchmark: (number | null)[];
  excess_pct: number | null;
};

/** The run's equity and the index on one axis: both rebased to 100 on the first day. */
function withBenchmark(
  chart: { dates: string[]; series: { name: string; data: (number | null)[] }[] },
  benchmark: Benchmark,
): { dates: string[]; series: { name: string; data: (number | null)[] }[] } {
  const indexName = benchmark.ts_code;
  return {
    dates: chart.dates,
    series: [...chart.series, { name: indexName, data: benchmark.benchmark }],
  };
}

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
  const [benchmarkCode, setBenchmarkCode] = useState('000300.SH');
  const [benchmarks, setBenchmarks] = useState<{ ts_code: string; name: string }[]>([]);
  const [benchmark, setBenchmark] = useState<Benchmark | null>(null);

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
    apiFetch<{ indexes: { ts_code: string; name: string }[] }>('/api/indexes')
      .then((d) => setBenchmarks((d.indexes ?? []).slice(0, 8)))
      .catch(() => setBenchmarks([]));
  }, []);

  useEffect(() => {
    if (!selectedRunId || !benchmarkCode) {
      setBenchmark(null);
      return;
    }
    apiFetch<Benchmark>(`/api/simulations/${selectedRunId}/benchmark?ts_code=${encodeURIComponent(benchmarkCode)}`)
      .then(setBenchmark)
      .catch(() => setBenchmark(null));
  }, [selectedRunId, benchmarkCode]);

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

  const tradeColumns: Column<Record<string, unknown>>[] = [
    { key: 'date', label: t('results.colDate'), render: (row) => String(row.date ?? '') },
    { key: 'ts_code', label: t('quote.col.ts_code'), render: (row) => String(row.ts_code ?? '') },
    { key: 'status', label: t('results.colStatus'), render: (row) => String(row.status ?? '') },
    {
      key: 'side',
      label: t('portfolio.colSide'),
      render: (row) => (row.side === 'buy' ? t('portfolio.sideBuy') : t('portfolio.sideSell')),
    },
    {
      key: 'shares',
      label: t('portfolio.colShares'),
      align: 'right',
      render: (row) => String(row.shares ?? ''),
    },
    { key: 'price', label: t('portfolio.colPrice'), align: 'right', render: (row) => String(row.price ?? '') },
    {
      key: 'benefit',
      label: t('results.colBenefit'),
      align: 'right',
      render: (row) => String(row.benefit ?? ''),
    },
    { key: 'reason', label: t('results.colReason'), render: (row) => String(row.reason ?? '') },
  ];

  return (
    <>
      <p className="text-muted mb-4">
        {t('results.subtitle')}
      </p>

      <div className="toolbar mb-4">
        <div className="form-row field-xwide field-xwide--min">
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
          <div className="form-row field-xwide field-xwide--min">
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

      {loadingRuns && <p className="text-muted">{t('results.loading')}</p>}

      {!loadingRuns && runs.length === 0 && (
        <div className="empty-panel">
          <p className="text-muted mb-3">{t('results.empty')}</p>
          <Link to="/simulation" className="btn btn-primary btn-sm">{t('simulation.tabRun')}</Link>
        </div>
      )}

      {compare.length > 1 && (
        <div className="mb-6">
          <h2 className="panel-title">{t('results.compareTitle')}</h2>
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
              <div className="toolbar mb-3">
                <div className="form-row field-medium">
                  <label htmlFor="benchmark-select">{t('results.benchmark')}</label>
                  <select
                    id="benchmark-select"
                    value={benchmarkCode}
                    onChange={(e) => setBenchmarkCode(e.target.value)}
                  >
                    <option value="">{t('results.noBenchmark')}</option>
                    {benchmarks.map((item) => (
                      <option key={item.ts_code} value={item.ts_code}>
                        {item.name}
                      </option>
                    ))}
                  </select>
                </div>
                {benchmark && benchmark.excess_pct != null && (
                  <span className={`text-sm ${benchmark.excess_pct >= 0 ? 'price-up' : 'price-down'}`}>
                    {t('results.excessVsBenchmark', { value: benchmark.excess_pct.toFixed(2) })}
                  </span>
                )}
              </div>
              <LineChart
                data={benchmark ? withBenchmark(chart, benchmark) : chart}
                title={run ? `Policy ${run.policy_id}` : undefined}
              />
            </div>
          )}
          {tab === 'trades' && (
            <DataTable
              pageSize={25}
              columns={tradeColumns}
              rows={trades.slice(-80)}
              rowKey={(row, i) => `${String(row.ts_code)}-${String(row.date)}-${i}`}
              empty={t('results.noTrades')}
            />
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
