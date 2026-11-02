import { useCallback, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { toast } from 'sonner';
import { apiFetch } from '../utils/api';
import { DataTable, type Column } from '../components/DataTable';
import './Datasets.scss';

type Dataset = { id: string; name: string; kind: string; description: string | null };
type Version = {
  version: number;
  status: string;
  files: number | null;
  rows: number | null;
  date_from: string | null;
  date_to: string | null;
  published_at: string | null;
};

/** 训练集放在 openKMS，这里只读：有哪些数据集、各有哪几个版本。 */
export function Datasets() {
  const { t } = useTranslation();
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [selected, setSelected] = useState('');
  const [versions, setVersions] = useState<Version[]>([]);

  const load = useCallback(async () => {
    try {
      const res = await apiFetch<{ datasets: Dataset[] }>('/api/datasets');
      setDatasets(res.datasets ?? []);
      setSelected((current) => current || res.datasets?.[0]?.id || '');
    } catch {
      toast.error(t('datasets.loadFailed'));
    }
  }, [t]);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    if (!selected) {
      setVersions([]);
      return;
    }
    apiFetch<{ versions: Version[] }>(`/api/datasets/${selected}`)
      .then((d) => setVersions(d.versions ?? []))
      .catch(() => setVersions([]));
  }, [selected]);

  const columns: Column<Dataset>[] = [
    {
      key: 'name',
      label: t('datasets.colName'),
      render: (row) => (
        <button type="button" className="btn btn-link" onClick={() => setSelected(row.id)}>
          {row.name}
        </button>
      ),
    },
    { key: 'kind', label: t('datasets.colKind'), render: (row) => row.kind },
  ];

  const versionColumns: Column<Version>[] = [
    { key: 'version', label: t('datasets.colVersion'), render: (row) => `v${row.version}` },
    { key: 'status', label: t('datasets.colStatus'), render: (row) => row.status },
    {
      key: 'coverage',
      label: t('datasets.colCoverage'),
      render: (row) => `${row.date_from ?? '—'} → ${row.date_to ?? '—'}`,
    },
    { key: 'rows', label: t('datasets.colRows'), align: 'right', render: (row) => row.rows?.toLocaleString() ?? '—' },
    { key: 'files', label: t('datasets.colFiles'), align: 'right', render: (row) => row.files ?? '—' },
    {
      key: 'published',
      label: t('datasets.colPublished'),
      render: (row) => (row.published_at ? row.published_at.slice(0, 10) : '—'),
    },
  ];

  return (
    <div className="datasets-page">
      <header className="datasets-header">
        <h1>{t('datasets.title')}</h1>
        <p className="datasets-lead">{t('datasets.lead')}</p>
      </header>

      <DataTable<Dataset>
        columns={columns}
        rows={datasets}
        rowKey={(row) => row.id}
        empty={t('datasets.empty')}
        pageSize={10}
      />

      {selected && (
        <section className="datasets-versions">
          <h2>{t('datasets.versionsTitle')}</h2>
          <p className="datasets-lead">{t('datasets.versionsHint')}</p>
          <DataTable<Version>
            columns={versionColumns}
            rows={versions}
            rowKey={(row) => String(row.version)}
            empty={t('datasets.noVersions')}
            pageSize={10}
          />
        </section>
      )}
    </div>
  );
}
