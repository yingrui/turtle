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

/** 第一层：只做一件事 —— 列出有哪些评分模型，点进去看详情。 */
export function Rankings({ embedded = false }: { embedded?: boolean } = {}) {
  const { t } = useTranslation();
  const [sources, setSources] = useState<Source[]>([]);

  const load = useCallback(async () => {
    try {
      const res = await apiFetch<{ sources: Source[] }>('/api/rankings');
      setSources(res.sources ?? []);
    } catch {
      toast.error(t('rankings.loadFailed'));
    }
  }, [t]);

  useEffect(() => {
    void load();
  }, [load]);

  const columns: Column<Source>[] = [
    {
      key: 'name',
      label: t('rankings.colName'),
      render: (row) => <Link to={`/methods/${row.id}`}>{row.display_name}</Link>,
    },
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
    {
      key: 'rows',
      label: t('rankings.colRows'),
      render: (row) => row.row_count?.toLocaleString() ?? '—',
    },
    { key: 'status', label: t('rankings.colStatus'), render: (row) => row.status },
  ];

  return (
    <div className={embedded ? 'rankings-body' : 'rankings-page'}>
      {!embedded && (
        <>
          <h1>{t('rankings.title')}</h1>
          <p className="rankings-subtitle">{t('rankings.subtitle')}</p>
        </>
      )}
      <DataTable<Source>
        columns={columns}
        rows={sources}
        rowKey={(row) => row.id}
        empty={t('rankings.empty')}
        pageSize={10}
      />
    </div>
  );
}
