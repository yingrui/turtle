import { useCallback, useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { toast } from 'sonner';
import { apiFetch } from '../utils/api';
import { DataTable, type Column } from '../components/DataTable';
import { useJobPoll } from '../hooks/useJobPoll';

type Factor = {
  code: string;
  name: string;
  category: string;
  direction: 'positive' | 'negative' | 'neutral';
  unit: string | null;
  logic: string | null;
  formula: string | null;
  params: Record<string, unknown>;
  lookback_days: number | null;
  ic_ir: number | null;
  source_ref: string | null;
  is_computable: boolean;
  value_count: number;
  stock_count: number;
  first_date: string | null;
  last_date: string | null;
};

type ValueRow = { ts_code: string; trade_date: string; value: number };

type Mode = 'stock' | 'date';

export function Factors() {
  const { t } = useTranslation();
  const [factors, setFactors] = useState<Factor[]>([]);
  const [loading, setLoading] = useState(false);
  const [search, setSearch] = useState('');
  const [category, setCategory] = useState('');
  const [computableOnly, setComputableOnly] = useState(false);
  const [selected, setSelected] = useState<Factor | null>(null);

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

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const query = new URLSearchParams();
      if (computableOnly) query.set('computable', 'true');
      if (category) query.set('category', category);
      const data = await apiFetch<{ factors: Factor[] }>(`/api/factors?${query.toString()}`);
      setFactors(data.factors);
      setSelected((current) => {
        if (current) {
          const updated = data.factors.find((f) => f.code === current.code);
          if (updated) return updated;
        }
        return data.factors.find((f) => f.is_computable && f.value_count > 0) ?? data.factors[0] ?? null;
      });
    } catch (err) {
      toast.error(err instanceof Error ? err.message : t('factor.loadFailed'));
    } finally {
      setLoading(false);
    }
  }, [computableOnly, category, t]);

  useEffect(() => {
    load();
  }, [load]);

  // A finished computation changes the coverage columns and may change what the table shows.
  useEffect(() => {
    if (job?.status === 'completed') {
      toast.success(t('factor.computeDone'));
      load();
      if (selected) loadValues(selected, { keepDates: true });
    }
    if (job?.status === 'failed') toast.error(job.error ?? t('factor.computeFailed'));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [job?.status]);

  const loadValues = useCallback(
    async (factor: Factor, opts: { keepDates?: boolean } = {}) => {
      setRowsLoading(true);
      try {
        const query = new URLSearchParams({ limit: '200' });
        if (mode === 'stock' && tsCode) query.set('ts_code', tsCode);
        if (mode === 'date' && tradeDate) query.set('trade_date', tradeDate);
        if (start) query.set('start', start);
        if (end) query.set('end', end);
        const data = await apiFetch<{ rows: ValueRow[]; total: number }>(
          `/api/factors/${encodeURIComponent(factor.code)}/values?${query.toString()}`,
        );
        setRows(data.rows);
        setRowTotal(data.total);
        if (!opts.keepDates && !tradeDate && data.rows[0]?.trade_date) {
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
    if (selected) loadValues(selected);
    else setRows([]);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selected?.code]);

  async function compute() {
    if (!selected) return;
    try {
      const query = new URLSearchParams();
      if (start) query.set('start', start);
      if (end) query.set('end', end);
      const res = await apiFetch<{ job_id: string }>(
        `/api/factors/${encodeURIComponent(selected.code)}/compute?${query.toString()}`,
        { method: 'POST' },
      );
      setJobId(res.job_id);
      toast.success(t('factor.computeStarted'));
    } catch (err) {
      toast.error(err instanceof Error ? err.message : t('factor.computeFailed'));
    }
  }

  const visible = useMemo(() => {
    const needle = search.trim().toLowerCase();
    if (!needle) return factors;
    return factors.filter(
      (f) =>
        f.code.toLowerCase().includes(needle) ||
        f.name.toLowerCase().includes(needle) ||
        (f.logic ?? '').toLowerCase().includes(needle),
    );
  }, [factors, search]);

  const categories = useMemo(
    () => Array.from(new Set(factors.map((f) => f.category))).sort(),
    [factors],
  );

  const factorColumns: Column<Factor>[] = [
    {
      key: 'code',
      label: t('factor.col.code'),
      sortable: true,
      sortValue: (row) => row.code,
      render: (row) => (
        <span>
          <strong>{row.code}</strong>
          {row.is_computable ? null : (
            <span style={{ color: 'var(--color-text-muted)', marginLeft: 6 }}>({t('factor.definitionOnly')})</span>
          )}
        </span>
      ),
    },
    {
      key: 'name',
      label: t('factor.col.name'),
      sortable: true,
      sortValue: (row) => row.name,
      render: (row) => row.name,
    },
    {
      key: 'category',
      label: t('factor.col.category'),
      sortable: true,
      sortValue: (row) => row.category,
      render: (row) => row.category,
    },
    {
      key: 'direction',
      label: t('factor.col.direction'),
      sortable: true,
      sortValue: (row) => row.direction,
      render: (row) => t(`factor.direction.${row.direction}`),
    },
    {
      key: 'last_date',
      label: t('factor.col.lastDate'),
      align: 'right',
      sortable: true,
      sortValue: (row) => row.last_date ?? '',
      render: (row) => row.last_date ?? '—',
    },
    {
      key: 'value_count',
      label: t('factor.col.values'),
      align: 'right',
      sortable: true,
      sortValue: (row) => row.value_count,
      render: (row) => row.value_count.toLocaleString(),
    },
  ];

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
      render: (row) => row.ts_code,
    },
    {
      key: 'value',
      label: selected?.code ?? t('factor.col.value'),
      align: 'right',
      sortable: true,
      sortValue: (row) => row.value,
      render: (row) => formatValue(row.value),
    },
  ];

  return (
    <div className="page-card">
      <h1 className="page-title">{t('nav.factor')}</h1>
      <p style={{ color: 'var(--color-text-muted)', marginBottom: 'var(--space-3)' }}>
        {t('factor.subtitle')}
      </p>

      <div style={{ display: 'flex', gap: 'var(--space-3)', flexWrap: 'wrap', alignItems: 'flex-end', marginBottom: 'var(--space-3)' }}>
        <div className="form-row" style={{ maxWidth: 220 }}>
          <label>{t('factor.search')}</label>
          <input type="search" value={search} onChange={(e) => setSearch(e.target.value)} placeholder="mom, 动量, EP" />
        </div>
        <div className="form-row" style={{ maxWidth: 180 }}>
          <label>{t('factor.col.category')}</label>
          <select value={category} onChange={(e) => setCategory(e.target.value)}>
            <option value="">{t('factor.allCategories')}</option>
            {categories.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
        </div>
        <label style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
          <input
            type="checkbox"
            checked={computableOnly}
            onChange={(e) => setComputableOnly(e.target.checked)}
          />
          {t('factor.computableOnly')}
        </label>
        <span style={{ color: 'var(--color-text-muted)', fontSize: 'var(--text-sm)' }}>
          {t('factor.counts', {
            total: factors.length,
            computable: factors.filter((f) => f.is_computable).length,
            shown: visible.length,
          })}
        </span>
      </div>

      <DataTable
        columns={factorColumns}
        rows={visible}
        rowKey={(row) => row.code}
        loading={loading}
        loadingLabel={t('factor.loading')}
        empty={t('factor.empty')}
        onRowClick={(row) => {
          setSelected(row);
          setRows([]);
        }}
        rowClassName={(row) => (row.code === selected?.code ? 'is-selected' : undefined)}
        defaultSortCol="code"
      />

      {selected && (
        <div
          style={{
            marginTop: 'var(--space-4)',
            padding: 'var(--space-3)',
            border: '1px solid var(--color-border)',
            borderRadius: 'var(--radius-md)',
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', gap: 'var(--space-3)', flexWrap: 'wrap' }}>
            <div>
              <h2 style={{ fontSize: 'var(--text-lg)', marginBottom: 4 }}>
                {selected.code} · {selected.name}
              </h2>
              <p style={{ fontSize: 'var(--text-sm)', color: 'var(--color-text-muted)' }}>
                {selected.logic ?? '—'}
                {selected.source_ref ? ` · ${selected.source_ref}` : ''}
                {selected.ic_ir != null ? ` · IC IR ${selected.ic_ir}` : ''}
              </p>
            </div>
            <div style={{ fontSize: 'var(--text-sm)', textAlign: 'right' }}>
              <div>
                {t('factor.coverage', {
                  stocks: selected.stock_count,
                  values: selected.value_count.toLocaleString(),
                })}
              </div>
              <div style={{ color: 'var(--color-text-muted)' }}>
                {selected.first_date ?? '—'} → {selected.last_date ?? '—'}
              </div>
            </div>
          </div>

          {selected.formula ? (
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
              {selected.formula}
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
              disabled={!selected.is_computable || job?.status === 'running' || job?.status === 'pending'}
            >
              {job?.status === 'running' || job?.status === 'pending'
                ? t('factor.computing')
                : t('factor.compute')}
            </button>
            <span style={{ fontSize: 'var(--text-sm)', color: 'var(--color-text-muted)' }}>
              {job?.status === 'completed' && job.result
                ? summarizeResult(job.result)
                : job?.status === 'running'
                  ? (job.log || '').split('\n').slice(-1)[0]
                  : ''}
            </span>
          </div>

          <div style={{ display: 'flex', gap: 'var(--space-3)', flexWrap: 'wrap', alignItems: 'flex-end', marginTop: 'var(--space-4)' }}>
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
                <input type="text" value={tsCode} onChange={(e) => setTsCode(e.target.value)} placeholder="600519.SH" />
              </div>
            ) : (
              <div className="form-row" style={{ maxWidth: 170 }}>
                <label>{t('factor.col.date')}</label>
                <input
                  type="date"
                  value={tradeDate}
                  onChange={(e) => setTradeDate(e.target.value)}
                  placeholder={selected.last_date ?? ''}
                />
              </div>
            )}
            <button
              type="button"
              className="btn btn-secondary"
              disabled={rowsLoading || selected.value_count === 0}
              onClick={() => loadValues(selected)}
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
              empty={selected.value_count === 0 ? t('factor.notComputedYet') : t('factor.noValues')}
              defaultSortCol="trade_date"
              defaultSortOrder="desc"
            />
          </div>
        </div>
      )}
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

function summarizeResult(result: string): string {
  try {
    const parsed = JSON.parse(result) as {
      factors?: { rows_written: number; stocks: number; dates: number }[];
    };
    const first = parsed.factors?.[0];
    if (!first) return '';
    return `${first.rows_written.toLocaleString()} values · ${first.stocks} stocks · ${first.dates} days`;
  } catch {
    return '';
  }
}
