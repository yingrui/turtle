import { useCallback, useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { toast } from 'sonner';
import { apiFetch } from '../utils/api';
import { DataTable, type Column } from '../components/DataTable';
import { useJobPoll } from '../hooks/useJobPoll';
import type { Factor } from './FactorList';

type ValueRow = { ts_code: string; trade_date: string; value: number };

type Mode = 'stock' | 'date';

/** One factor: what it means, how to compute it, and the values it has produced. */
export function FactorDetail() {
  const { t } = useTranslation();
  const { code = '' } = useParams();
  const [factor, setFactor] = useState<Factor | null>(null);
  const [notFound, setNotFound] = useState(false);
  const [loading, setLoading] = useState(true);

  const [mode, setMode] = useState<Mode>('stock');
  const [tsCode, setTsCode] = useState('600519.SH');
  const [tradeDate, setTradeDate] = useState('');
  const [start, setStart] = useState('');
  const [end, setEnd] = useState('');
  const [rows, setRows] = useState<ValueRow[]>([]);
  const [rowTotal, setRowTotal] = useState(0);
  const [rowsLoading, setRowsLoading] = useState(false);

  const [jobId, setJobId] = useState<string | null>(null);
  const job = useJobPoll(jobId);

  const loadFactor = useCallback(async () => {
    setLoading(true);
    setNotFound(false);
    try {
      const data = await apiFetch<Factor>(`/api/factors/${encodeURIComponent(code)}`);
      setFactor(data);
      return data;
    } catch (err) {
      setFactor(null);
      setNotFound(true);
      toast.error(err instanceof Error ? err.message : t('factor.loadFailed'));
      return null;
    } finally {
      setLoading(false);
    }
  }, [code, t]);

  const loadValues = useCallback(
    async (current: Factor) => {
      setRowsLoading(true);
      try {
        const query = new URLSearchParams({ limit: '200' });
        if (mode === 'stock' && tsCode) query.set('ts_code', tsCode);
        if (mode === 'date' && tradeDate) query.set('trade_date', tradeDate);
        if (start) query.set('start', start);
        if (end) query.set('end', end);
        const data = await apiFetch<{ rows: ValueRow[]; total: number }>(
          `/api/factors/${encodeURIComponent(current.code)}/values?${query.toString()}`,
        );
        setRows(data.rows);
        setRowTotal(data.total);
        if (mode === 'date' && !tradeDate && data.rows[0]?.trade_date) {
          setTradeDate(data.rows[0].trade_date);
        }
      } catch (err) {
        toast.error(err instanceof Error ? err.message : t('factor.valuesFailed'));
      } finally {
        setRowsLoading(false);
      }
    },
    [mode, tsCode, tradeDate, start, end, t],
  );

  useEffect(() => {
    setRows([]);
    setRowTotal(0);
    setJobId(null);
    loadFactor().then((data) => {
      if (data) loadValues(data);
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [code]);

  useEffect(() => {
    if (job?.status === 'completed') {
      toast.success(t('factor.computeDone'));
      loadFactor().then((data) => {
        if (data) loadValues(data);
      });
    }
    if (job?.status === 'failed') toast.error(job.error ?? t('factor.computeFailed'));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [job?.status]);

  async function compute() {
    if (!factor) return;
    try {
      const query = new URLSearchParams();
      if (start) query.set('start', start);
      if (end) query.set('end', end);
      const res = await apiFetch<{ job_id: string }>(
        `/api/factors/${encodeURIComponent(factor.code)}/compute?${query.toString()}`,
        { method: 'POST' },
      );
      setJobId(res.job_id);
      toast.success(t('factor.computeStarted'));
    } catch (err) {
      toast.error(err instanceof Error ? err.message : t('factor.computeFailed'));
    }
  }

  const valueColumns: Column<ValueRow>[] = [
    {
      key: 'trade_date',
      label: t('factor.col.date'),
      sortable: true,
      sortValue: (row) => row.trade_date,
      render: (row) => row.trade_date,
    },
    {
      key: 'ts_code',
      label: t('factor.col.stock'),
      sortable: true,
      sortValue: (row) => row.ts_code,
      render: (row) => <Link to={`/stocks/${encodeURIComponent(row.ts_code)}`}>{row.ts_code}</Link>,
    },
    {
      key: 'value',
      label: factor?.code ?? t('factor.col.value'),
      align: 'right',
      sortable: true,
      sortValue: (row) => row.value,
      render: (row) => formatValue(row.value),
    },
  ];

  if (notFound) {
    return (
      <div className="page-card">
        <h1 className="page-title">{t('factor.notFoundTitle')}</h1>
        <p>{t('factor.notFound', { code })}</p>
        <Link to="/factor">{t('factor.back')}</Link>
      </div>
    );
  }

  if (loading || !factor) {
    return (
      <div className="page-card">
        <p>{t('factor.loading')}</p>
      </div>
    );
  }

  return (
    <div className="page-card">
      <p style={{ fontSize: 'var(--text-sm)', marginBottom: 'var(--space-2)' }}>
        <Link to="/factor">← {t('factor.back')}</Link>
      </p>

      <div style={{ display: 'flex', justifyContent: 'space-between', gap: 'var(--space-3)', flexWrap: 'wrap' }}>
        <div>
          <h1 className="page-title" style={{ marginBottom: 4 }}>
            {factor.code} · {factor.name}
          </h1>
          <p style={{ fontSize: 'var(--text-sm)', color: 'var(--color-text-muted)' }}>
            {factor.logic ?? '—'}
            {factor.source_ref ? ` · ${factor.source_ref}` : ''}
            {factor.ic_ir != null ? ` · IC IR ${factor.ic_ir}` : ''}
            {` · ${t(`factor.direction.${factor.direction}`)}`}
          </p>
        </div>
        <div style={{ fontSize: 'var(--text-sm)', textAlign: 'right' }}>
          <div>
            {t('factor.coverage', {
              stocks: factor.stock_count,
              values: factor.value_count.toLocaleString(),
            })}
          </div>
          <div style={{ color: 'var(--color-text-muted)' }}>
            {factor.first_date ?? '—'} → {factor.last_date ?? '—'}
          </div>
        </div>
      </div>

      {factor.formula ? (
        <code
          style={{
            display: 'block',
            margin: 'var(--space-3) 0',
            padding: 'var(--space-2)',
            background: 'var(--color-surface-alt, rgba(0,0,0,0.04))',
            borderRadius: 'var(--radius-sm)',
            fontSize: 'var(--text-sm)',
          }}
        >
          {factor.formula}
        </code>
      ) : (
        <p style={{ margin: 'var(--space-3) 0', fontSize: 'var(--text-sm)', color: 'var(--color-warning, #b45309)' }}>
          {t('factor.noFormula')}
        </p>
      )}

      <div style={{ display: 'flex', gap: 'var(--space-3)', flexWrap: 'wrap', alignItems: 'flex-end' }}>
        <div className="form-row" style={{ maxWidth: 150 }}>
          <label>{t('factor.start')}</label>
          <input type="date" value={start} onChange={(e) => setStart(e.target.value)} />
        </div>
        <div className="form-row" style={{ maxWidth: 150 }}>
          <label>{t('factor.end')}</label>
          <input type="date" value={end} onChange={(e) => setEnd(e.target.value)} />
        </div>
        <button
          type="button"
          className="btn btn-primary"
          onClick={compute}
          disabled={!factor.is_computable || job?.status === 'running' || job?.status === 'pending'}
        >
          {job?.status === 'running' || job?.status === 'pending'
            ? t('factor.computing')
            : t('factor.compute')}
        </button>
        <span style={{ fontSize: 'var(--text-sm)', color: 'var(--color-text-muted)' }}>
          {job?.status === 'completed' && job.result
            ? summarizeResult(job.result, t)
            : job?.status === 'running'
              ? (job.log || '').split('\n').slice(-1)[0]
              : ''}
        </span>
      </div>

      <div
        style={{
          display: 'flex',
          gap: 'var(--space-3)',
          flexWrap: 'wrap',
          alignItems: 'flex-end',
          marginTop: 'var(--space-4)',
        }}
      >
        <div style={{ display: 'flex', gap: 'var(--space-2)' }}>
          <button
            type="button"
            className={`btn btn-sm ${mode === 'stock' ? 'btn-primary' : 'btn-secondary'}`}
            onClick={() => {
              setMode('stock');
              setTradeDate('');
            }}
          >
            {t('factor.modeStock')}
          </button>
          <button
            type="button"
            className={`btn btn-sm ${mode === 'date' ? 'btn-primary' : 'btn-secondary'}`}
            onClick={() => {
              setMode('date');
              setRows([]);
            }}
          >
            {t('factor.modeDate')}
          </button>
        </div>
        {mode === 'stock' ? (
          <div className="form-row" style={{ maxWidth: 180 }}>
            <label>{t('factor.col.stock')}</label>
            <input
              type="text"
              value={tsCode}
              onChange={(e) => setTsCode(e.target.value)}
              placeholder="600519.SH"
            />
          </div>
        ) : (
          <div className="form-row" style={{ maxWidth: 170 }}>
            <label>{t('factor.col.date')}</label>
            <input
              type="date"
              value={tradeDate}
              onChange={(e) => setTradeDate(e.target.value)}
              placeholder={factor.last_date ?? ''}
            />
          </div>
        )}
        <button
          type="button"
          className="btn btn-secondary"
          disabled={rowsLoading || factor.value_count === 0}
          onClick={() => loadValues(factor)}
        >
          {rowsLoading ? t('factor.loading') : t('factor.query')}
        </button>
        {rowTotal > 0 && (
          <span style={{ fontSize: 'var(--text-sm)', color: 'var(--color-text-muted)' }}>
            {t('factor.matches', { total: rowTotal.toLocaleString() })}
          </span>
        )}
      </div>

      <div style={{ marginTop: 'var(--space-3)' }}>
        <DataTable
          columns={valueColumns}
          rows={rows}
          rowKey={(row) => `${row.trade_date}-${row.ts_code}`}
          loading={rowsLoading}
          loadingLabel={t('factor.loading')}
          empty={factor.value_count === 0 ? t('factor.notComputedYet') : t('factor.noValues')}
          defaultSortCol="trade_date"
          defaultSortOrder="desc"
        />
      </div>
    </div>
  );
}

function formatValue(value: number): string {
  if (value === 0) return '0';
  const abs = Math.abs(value);
  if (abs < 0.0001) return value.toExponential(2);
  if (abs >= 1000) return value.toLocaleString(undefined, { maximumFractionDigits: 2 });
  return value.toFixed(4);
}

function summarizeResult(result: string, t: (key: string, opts?: Record<string, unknown>) => string): string {
  try {
    const parsed = JSON.parse(result) as {
      factors?: { rows_written: number; stocks: number; dates: number }[];
    };
    const first = parsed.factors?.[0];
    if (!first) return '';
    return t('factor.computeSummary', {
      values: first.rows_written.toLocaleString(),
      stocks: first.stocks,
      dates: first.dates,
    });
  } catch {
    return '';
  }
}
