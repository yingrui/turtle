import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useSearchParams } from 'react-router-dom';
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

export function SimulationResults() {
  const { t } = useTranslation();
  const [searchParams] = useSearchParams();
  const jobIdParam = searchParams.get('job_id');
  const [runs, setRuns] = useState<Run[]>([]);
  const [selectedRun, setSelectedRun] = useState('');
  const [tab, setTab] = useState('chart');
  const [summary, setSummary] = useState<Summary | null>(null);
  const [chart, setChart] = useState<{ dates: string[]; series: { name: string; data: (number | null)[] }[] } | null>(null);
  const [trades, setTrades] = useState<Record<string, unknown>[]>([]);
  const [benefit, setBenefit] = useState<Record<string, unknown>[]>([]);
  const [winLoss, setWinLoss] = useState<{ win: number; loss: number; holding: number } | null>(null);
  const [compare, setCompare] = useState<CompareRow[]>([]);

  useEffect(() => {
    const q = jobIdParam ? `?job_id=${jobIdParam}` : '';
    apiFetch<{ runs: Run[] }>(`/api/simulations${q}`).then((d) => {
      setRuns(d.runs);
      if (d.runs.length) setSelectedRun(d.runs[0].id);
    });
    if (jobIdParam) {
      apiFetch<{ policies: CompareRow[] }>(`/api/simulations/compare?job_id=${jobIdParam}`).then((d) =>
        setCompare(d.policies),
      );
    } else {
      setCompare([]);
    }
  }, [jobIdParam]);

  useEffect(() => {
    if (!selectedRun) return;
    apiFetch<Summary>(`/api/simulations/${selectedRun}/summary`).then(setSummary).catch(() => setSummary(null));
    apiFetch<{ dates: string[]; series: { name: string; data: (number | null)[] }[] }>(
      `/api/simulations/${selectedRun}/daily`,
    ).then(setChart);
    apiFetch<{ trades: Record<string, unknown>[] }>(`/api/simulations/${selectedRun}/trades`).then((d) =>
      setTrades(d.trades),
    );
    apiFetch<{ benefit: Record<string, unknown>[] }>(`/api/simulations/${selectedRun}/benefit`).then((d) =>
      setBenefit(d.benefit),
    );
    apiFetch<{ win: number; loss: number; holding: number }>(`/api/simulations/${selectedRun}/win-loss`).then(
      setWinLoss,
    );
  }, [selectedRun]);

  const run = runs.find((r) => r.id === selectedRun);

  return (
    <div className="page-card">
      <h1 className="page-title">{t('nav.results')}</h1>
      <div className="form-row" style={{ maxWidth: 480 }}>
        <label htmlFor="run">Simulation run</label>
        <select id="run" value={selectedRun} onChange={(e) => setSelectedRun(e.target.value)}>
          {runs.map((r) => (
            <option key={r.id} value={r.id}>
              {r.portfolio_name} — policy {r.policy_id} ({r.started_at?.slice(0, 10)})
            </option>
          ))}
        </select>
      </div>

      {compare.length > 1 && (
        <div style={{ marginBottom: 'var(--space-6)' }}>
          <h2 style={{ fontSize: 'var(--text-lg)', marginBottom: 'var(--space-3)' }}>Policy comparison (same job)</h2>
          <table className="data-table">
            <thead>
              <tr>
                <th>Policy</th>
                <th>CAGR</th>
                <th>Return %</th>
                <th>Final</th>
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
          <div className="stat-card"><span>Return</span><strong>{summary.return_rate_pct}%</strong></div>
          <div className="stat-card"><span>Wins</span><strong>{winLoss.win}</strong></div>
          <div className="stat-card"><span>Losses</span><strong>{winLoss.loss}</strong></div>
        </div>
      )}

      <Tabs
        tabs={[
          { id: 'chart', label: 'Equity curve' },
          { id: 'trades', label: 'Trades' },
          { id: 'benefit', label: 'By stock' },
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
                <th>Date</th>
                <th>Code</th>
                <th>Status</th>
                <th>Buy</th>
                <th>Sell</th>
                <th>Benefit</th>
                <th>Reason</th>
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
                <th>Code</th>
                <th>Total benefit</th>
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
    </div>
  );
}
