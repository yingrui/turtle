import { useCallback, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { apiFetch } from '../../utils/api';
import { DataTable, type Column } from '../DataTable';
import './RunHoldingsPanel.scss';

type Run = {
  id: string;
  name: string | null;
  window_start: string | null;
  window_end: string | null;
  finished_at: string | null;
};

type Holding = {
  ts_code: string;
  shares: number;
  price: number;
  avg_cost: number | null;
  unrealized_pnl: number | null;
  unrealized_pct: number | null;
  weight: number | null;
  opened_at: string | null;
  holding_days: number | null;
};

/**
 * What a backtest held on a chosen day. A portfolio's holdings only make sense together with the run
 * they came from and the date being looked at, so the three are chosen together.
 */
export function RunHoldingsPanel({ portfolio }: { portfolio: string }) {
  const { t } = useTranslation();
  const [runs, setRuns] = useState<Run[]>([]);
  const [runId, setRunId] = useState('');
  const [dates, setDates] = useState<string[]>([]);
  const [day, setDay] = useState('');
  const [rows, setRows] = useState<Holding[]>([]);

  useEffect(() => {
    if (!portfolio) return;
    apiFetch<{ runs: Run[] }>('/api/simulations')
      .then((d) => {
        const mine = (d.runs ?? []).filter((run) => run.finished_at);
        setRuns(mine);
        setRunId(mine[0]?.id ?? '');
      })
      .catch(() => setRuns([]));
  }, [portfolio]);

  useEffect(() => {
    if (!runId) {
      setDates([]);
      setRows([]);
      return;
    }
    apiFetch<{ dates: string[] }>(`/api/simulations/${runId}/holding-dates`)
      .then((d) => {
        const days = d.dates ?? [];
        setDates(days);
        setDay(days[days.length - 1] ?? '');
      })
      .catch(() => setDates([]));
  }, [runId]);

  const load = useCallback(async () => {
    if (!runId || !day) {
      setRows([]);
      return;
    }
    try {
      const d = await apiFetch<{ holdings: Holding[] }>(
        `/api/simulations/${runId}/holdings?day=${encodeURIComponent(day)}`,
      );
      setRows(d.holdings ?? []);
    } catch {
      setRows([]);
    }
  }, [runId, day]);

  useEffect(() => {
    void load();
  }, [load]);

  function money(value: number | null | undefined) {
    return value == null ? '—' : value.toLocaleString(undefined, { maximumFractionDigits: 2 });
  }

  const columns: Column<Holding>[] = [
    { key: 'code', label: t('portfolio.colCode'), render: (row) => row.ts_code },
    { key: 'shares', label: t('portfolio.colShares'), align: 'right', render: (row) => row.shares },
    { key: 'cost', label: t('portfolio.colAvgCost'), align: 'right', render: (row) => money(row.avg_cost) },
    { key: 'price', label: t('portfolio.colLastPrice'), align: 'right', render: (row) => money(row.price) },
    {
      key: 'pnl',
      label: t('portfolio.colUnrealized'),
      align: 'right',
      render: (row) => (
        <span className={(row.unrealized_pnl ?? 0) >= 0 ? 'price-up' : 'price-down'}>
          {money(row.unrealized_pnl)}
          {row.unrealized_pct == null ? '' : `（${row.unrealized_pct.toFixed(2)}%）`}
        </span>
      ),
    },
    {
      key: 'weight',
      label: t('portfolio.colWeight'),
      align: 'right',
      render: (row) => (row.weight == null ? '—' : `${(row.weight * 100).toFixed(2)}%`),
    },
    { key: 'opened', label: t('portfolio.colOpened'), render: (row) => row.opened_at ?? '—' },
    {
      key: 'days',
      label: t('portfolio.colHoldingDays'),
      align: 'right',
      render: (row) => row.holding_days ?? '—',
    },
  ];

  return (
    <div className="run-holdings">
      <div className="toolbar">
        <div className="form-row field-wide">
          <label htmlFor="rh-run">{t('portfolio.pickRun')}</label>
          <select id="rh-run" value={runId} onChange={(e) => setRunId(e.target.value)}>
            {runs.map((run) => (
              <option key={run.id} value={run.id}>
                {run.name || run.id.slice(0, 8)} · {run.window_start ?? '—'} → {run.window_end ?? '—'}
              </option>
            ))}
          </select>
        </div>
        <div className="form-row field-medium">
          <label htmlFor="rh-day">{t('portfolio.pickDay')}</label>
          <select id="rh-day" value={day} onChange={(e) => setDay(e.target.value)}>
            {dates.slice().reverse().map((value) => (
              <option key={value} value={value}>
                {value}
              </option>
            ))}
          </select>
        </div>
      </div>

      <h2 className="portfolio-panel-title">
        {t('portfolio.runHoldingsTitle', { day: day || '—' })}
      </h2>
      <p className="portfolio-panel-desc">{t('portfolio.runHoldingsDesc')}</p>
      <DataTable<Holding>
        columns={columns}
        rows={rows}
        rowKey={(row) => row.ts_code}
        empty={t('portfolio.emptyHoldings')}
        pageSize={25}
      />
    </div>
  );
}
