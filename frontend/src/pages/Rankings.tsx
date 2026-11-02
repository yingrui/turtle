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
  const [withControls, setWithControls] = useState(false);

  const load = useCallback(async () => {
    try {
      const res = await apiFetch<{ sources: Source[] }>(
        `/api/rankings?include_controls=${withControls}`,
      );
      setSources(res.sources ?? []);
    } catch {
      toast.error(t('rankings.loadFailed'));
    }
  }, [t, withControls]);

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
      // 打分表存的是"每天每只股票一条"，所以条数 = 交易日 × 股票数；
      // 逐月模型不存分数，是当天现算的，没有条数可报。
      render: (row) =>
        row.kind === 'model'
          ? t('rankings.onTheFly', { periods: (row as { params?: { periods?: unknown[] } }).params?.periods?.length ?? '—' })
          : (row.row_count?.toLocaleString() ?? '—'),
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
      <label className="rankings-toggle">
        <input
          type="checkbox"
          checked={withControls}
          onChange={(event) => setWithControls(event.target.checked)}
        />
        {t('rankings.showControls')}
      </label>

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
