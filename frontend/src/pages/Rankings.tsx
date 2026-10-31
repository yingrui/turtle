import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { toast } from 'sonner';
import { apiFetch } from '../utils/api';
import { DataTable, type Column } from '../components/DataTable';
import './Rankings.scss';

type Source = {
  id: string;
  kind: string;
  display_name: string;
  description: string;
  method: string | null;
  row_count: number | null;
  date_from: string | null;
  date_to: string | null;
  dataset: { name: string | null; version: number | null };
  status: string;
  artifact_sha256: string;
  validation?: { ok?: boolean };
};

type RankRow = { ts_code: string; score: number; rank: number };

export function Rankings() {
  const { t } = useTranslation();
  const [sources, setSources] = useState<Source[]>([]);
  const [selected, setSelected] = useState<string>('');
  const [day, setDay] = useState<string>('');
  const [rows, setRows] = useState<RankRow[]>([]);


  const load = useCallback(async () => {
    try {
      const res = await apiFetch<{ sources: Source[] }>('/api/rankings');
      setSources(res.sources);
      setSelected((current) => current || res.sources[0]?.id || '');
    } catch {
      toast.error(t('rankings.loadFailed'));
    }
  }, [t]);

  useEffect(() => {
    void load();
  }, [load]);

  const preview = useCallback(async () => {
    if (!selected) return;
    const query = day ? `?day=${day}&limit=20` : '?limit=20';
    try {
      const res = await apiFetch<{ rows: RankRow[] }>(`/api/rankings/${selected}/preview${query}`);
      setRows(res.rows);
    } catch (error) {
      setRows([]);
      toast.error(error instanceof Error ? error.message : t('rankings.previewFailed'));
    }
  }, [selected, day, t]);

  useEffect(() => {
    void preview();
  }, [preview]);

  const columns: Column<Source>[] = [
    { key: 'name', label: t('rankings.colName'), render: (row) => row.display_name },
    { key: 'kind', label: t('rankings.colKind'), render: (row) => row.kind },
    {
      key: 'coverage',
      label: t('rankings.colCoverage'),
      render: (row) => `${row.date_from ?? '—'} → ${row.date_to ?? '—'}`,
    },
    {
      key: 'dataset',
      label: t('rankings.colDataset'),
      render: (row) =>
        row.dataset?.name ? `${row.dataset.name} v${row.dataset.version ?? '?'}` : '—',
    },
    { key: 'rows', label: t('rankings.colRows'), render: (row) => row.row_count?.toLocaleString() ?? '—' },
    { key: 'status', label: t('rankings.colStatus'), render: (row) => row.status },
  ];

  const rankColumns: Column<RankRow>[] = [
    { key: 'rank', label: '#', render: (row) => row.rank },
    { key: 'code', label: t('rankings.colCode'), render: (row) => row.ts_code },
    { key: 'score', label: t('rankings.colScore'), render: (row) => row.score.toFixed(3) },
  ];

  return (
    <div className="rankings-page">
      <h1>{t('rankings.title')}</h1>
      <p className="rankings-subtitle">{t('rankings.subtitle')}</p>

      <DataTable<Source>
        columns={columns}
        rows={sources}
        rowKey={(row) => row.id}
        empty={t('rankings.empty')}
        pageSize={10}
      />

      <p className="rankings-hint">
        <Link to="/analyses">{t('rankings.generateElsewhere')}</Link>
      </p>

      <div className="rankings-preview">
        <div className="form-row">
          <label htmlFor="rankings-source">{t('rankings.source')}</label>
          <select
            id="rankings-source"
            value={selected}
            onChange={(event) => setSelected(event.target.value)}
          >
            {sources.map((source) => (
              <option key={source.id} value={source.id}>
                {source.display_name}
              </option>
            ))}
          </select>
        </div>
        <div className="form-row">
          <label htmlFor="rankings-day">{t('rankings.day')}</label>
          <input
            id="rankings-day"
            type="date"
            value={day}
            onChange={(event) => setDay(event.target.value)}
          />
        </div>
        <button type="button" className="btn btn-secondary" onClick={preview} disabled={!selected}>
          {t('rankings.preview')}
        </button>

        <DataTable<RankRow>
          columns={rankColumns}
          rows={rows}
          rowKey={(row) => row.ts_code}
          empty={t('rankings.previewEmpty')}
          pageSize={10}
        />
      </div>
    </div>
  );
}
