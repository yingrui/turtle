import { useCallback, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { toast } from 'sonner';
import { apiFetch } from '../utils/api';
import { DataTable, type Column } from '../components/DataTable';
import './SimulationRuns.scss';

type RunRow = {
  id: string;
  name: string | null;
  mode?: string | null;
  pool_mode?: string | null;
  started_at: string | null;
  finished_at: string | null;
  window_start?: string | null;
  window_end?: string | null;
  return_rate_pct?: number | null;
  trade_count?: number | null;
};

/** The list is the entry point: pick a run, or start a new one. */
export function SimulationRuns() {
  const { t } = useTranslation();
  const [runs, setRuns] = useState<RunRow[]>([]);

  const load = useCallback(async () => {
    try {
      const res = await apiFetch<{ runs: RunRow[] }>('/api/simulations');
      setRuns(res.runs ?? []);
    } catch {
      toast.error(t('simulation.loadFailed'));
    }
  }, [t]);

  useEffect(() => {
    void load();
  }, [load]);

  const columns: Column<RunRow>[] = [
    {
      key: 'name',
      label: t('simulation.colRun'),
      render: (row) => (
        <Link to={`/simulation/results?run_id=${encodeURIComponent(row.id)}`}>
          {row.name || row.id.slice(0, 8)}
        </Link>
      ),
    },
    { key: 'mode', label: t('simulation.colMode'), render: (row) => row.mode ?? 'signal' },
    {
      key: 'window',
      label: t('simulation.colWindow'),
      render: (row) =>
        row.window_start && row.window_end ? `${row.window_start} → ${row.window_end}` : '—',
    },
    {
      key: 'trades',
      label: t('simulation.colTrades'),
      render: (row) => (row.trade_count == null ? '—' : row.trade_count.toLocaleString()),
    },
    {
      key: 'return',
      label: t('simulation.colReturn'),
      render: (row) => (row.return_rate_pct == null ? '—' : `${row.return_rate_pct.toFixed(2)}%`),
    },
    {
      key: 'status',
      label: t('simulation.colStatus'),
      render: (row) => (
        <span className={row.finished_at ? 'simulation-run-done' : 'simulation-run-open'}>
          {row.finished_at ? t('simulation.runDone') : t('simulation.runOpen')}
        </span>
      ),
    },
  ];

  return (
    <div className="simulation-runs-page">
      <div className="simulation-runs-header">
        <p className="simulation-runs-subtitle">{t('simulation.listSubtitle')}</p>
        <Link className="btn btn-primary" to="/simulation/new">
          {t('simulation.newRun')}
        </Link>
      </div>
      <DataTable<RunRow>
        columns={columns}
        rows={runs}
        rowKey={(row) => row.id}
        empty={t('simulation.noRuns')}
        pageSize={20}
      />
    </div>
  );
}
