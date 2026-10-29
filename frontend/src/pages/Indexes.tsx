import { useCallback, useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { toast } from 'sonner';
import { apiFetch } from '../utils/api';
import { CandlestickChart, type OhlcvData } from '../components/Chart';
import { DataTable, type Column } from '../components/DataTable';
import './Indexes.scss';

type IndexItem = {
  ts_code: string;
  name: string;
  market: string | null;
  category: string | null;
  latest_date: string | null;
  bars: number;
  close: number | null;
  pct_chg: number | null;
};

type IndexDaily = OhlcvData & { ts_code: string; pct_chg: number[]; pre_close: number[]; amount: number[] };

const RANGES = [
  { key: '3M', months: 3 },
  { key: '6M', months: 6 },
  { key: '1Y', months: 12 },
  { key: '3Y', months: 36 },
] as const;

function rangeStart(months: number): string {
  const start = new Date();
  start.setMonth(start.getMonth() - months);
  return start.toISOString().slice(0, 10);
}

function formatPoints(value: number | null | undefined): string {
  if (value == null) return '—';
  return value.toLocaleString(undefined, { maximumFractionDigits: 2 });
}

function formatPct(value: number | null | undefined): string {
  if (value == null) return '—';
  return `${value > 0 ? '+' : ''}${value.toFixed(2)}%`;
}

/**
 * Indexes: the market's own series. The list is small on purpose — only indexes that carry daily bars
 * appear (the feed has ten thousand names and bars for a few dozen), and the broad benchmarks lead.
 */
export function Indexes() {
  const { t } = useTranslation();
  const [indexes, setIndexes] = useState<IndexItem[]>([]);
  const [selected, setSelected] = useState<string>('');
  const [range, setRange] = useState<(typeof RANGES)[number]['key']>('6M');
  const [daily, setDaily] = useState<IndexDaily | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    apiFetch<{ indexes: IndexItem[] }>('/api/indexes')
      .then((data) => {
        setIndexes(data.indexes);
        if (data.indexes[0]) setSelected((current) => current || data.indexes[0].ts_code);
      })
      .catch((err) => toast.error(err instanceof Error ? err.message : t('indexes.loadFailed')));
  }, [t]);

  const load = useCallback(async () => {
    if (!selected) return;
    setLoading(true);
    try {
      const months = RANGES.find((item) => item.key === range)?.months ?? 6;
      const data = await apiFetch<IndexDaily>(
        `/api/indexes/${encodeURIComponent(selected)}/daily?start=${rangeStart(months)}`,
      );
      setDaily(data);
    } catch (err) {
      setDaily(null);
      toast.error(err instanceof Error ? err.message : t('indexes.loadFailed'));
    } finally {
      setLoading(false);
    }
  }, [selected, range, t]);

  useEffect(() => {
    load();
  }, [load]);

  const current = useMemo(() => indexes.find((item) => item.ts_code === selected), [indexes, selected]);

  const columns: Column<IndexItem>[] = [
    {
      key: 'name',
      label: t('indexes.colName'),
      sortable: true,
      sortValue: (row) => row.name,
      render: (row) => row.name,
    },
    {
      key: 'ts_code',
      label: t('indexes.colCode'),
      sortable: true,
      sortValue: (row) => row.ts_code,
      render: (row) => <span className="text-muted">{row.ts_code}</span>,
    },
    {
      key: 'close',
      label: t('indexes.colClose'),
      align: 'right',
      sortable: true,
      sortValue: (row) => row.close ?? 0,
      render: (row) => formatPoints(row.close),
    },
    {
      key: 'pct_chg',
      label: t('indexes.colPct'),
      align: 'right',
      sortable: true,
      defaultOrder: 'desc',
      sortValue: (row) => row.pct_chg ?? 0,
      render: (row) => (
        <span className={(row.pct_chg ?? 0) > 0 ? 'price-up' : (row.pct_chg ?? 0) < 0 ? 'price-down' : ''}>
          {formatPct(row.pct_chg)}
        </span>
      ),
    },
  ];

  return (
    <div className="page-card">
      <h1 className="page-title">{t('nav.indexes')}</h1>
      <p className="page-subtitle">{t('indexes.subtitle')}</p>

      <div className="indexes-layout">
        <div className="indexes-list">
          <DataTable
            pageSize={25}
            columns={columns}
            rows={indexes}
            rowKey={(row) => row.ts_code}
            loading={indexes.length === 0}
            loadingLabel={t('indexes.loading')}
            empty={t('indexes.empty')}
            onRowClick={(row) => setSelected(row.ts_code)}
            rowClassName={(row) => (row.ts_code === selected ? 'is-selected' : undefined)}
            defaultSortCol="pct_chg"
            defaultSortOrder="desc"
          />
        </div>

        <div className="indexes-chart">
          {current ? (
            <>
              <div className="split-row">
                <div>
                  <h2 className="panel-title">
                    {current.name} <span className="text-muted text-sm">{current.ts_code}</span>
                  </h2>
                  <p className="text-hint">
                    {t('indexes.meta', { category: current.category ?? '—', bars: current.bars })}
                  </p>
                </div>
                <div className="meta-block">
                  <div className="text-sm">{formatPoints(current.close)}</div>
                  <div
                    className={
                      (current.pct_chg ?? 0) > 0 ? 'price-up' : (current.pct_chg ?? 0) < 0 ? 'price-down' : ''
                    }
                  >
                    {formatPct(current.pct_chg)}
                  </div>
                </div>
              </div>

              <div className="toolbar toolbar--tight mt-3">
                {RANGES.map((item) => (
                  <button
                    key={item.key}
                    type="button"
                    className={`btn btn-sm ${range === item.key ? 'btn-primary' : 'btn-secondary'}`}
                    onClick={() => setRange(item.key)}
                  >
                    {item.key}
                  </button>
                ))}
              </div>

              <div className="chart-container mt-3">
                {loading ? (
                  <p className="text-muted">{t('indexes.loading')}</p>
                ) : daily && daily.dates.length > 0 ? (
                  <CandlestickChart data={daily} />
                ) : (
                  <p className="text-muted">{t('indexes.noData')}</p>
                )}
              </div>
            </>
          ) : (
            <p className="text-muted">{t('indexes.pick')}</p>
          )}
        </div>
      </div>
    </div>
  );
}
