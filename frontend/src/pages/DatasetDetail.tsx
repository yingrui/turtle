import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, useParams } from 'react-router-dom';
import { apiFetch } from '../utils/api';
import { DataTable, type Column } from '../components/DataTable';
import './Datasets.scss';

type Version = {
  version: number;
  status: string;
  files: number | null;
  rows: number | null;
  date_from: string | null;
  date_to: string | null;
  published_at: string | null;
};

/** 第二层：这个数据集有哪几个版本，哪一个还能引用。 */
export function DatasetDetail() {
  const { t } = useTranslation();
  const { id = '' } = useParams();
  const [versions, setVersions] = useState<Version[]>([]);
  const [name, setName] = useState('');

  useEffect(() => {
    apiFetch<{ versions: Version[]; name: string | null }>(`/api/datasets/${encodeURIComponent(id)}`)
      .then((d) => {
        setName(d.name ?? id.slice(0, 8));
        setVersions((d.versions ?? []).sort((a, b) => b.version - a.version));
      })
      .catch(() => setVersions([]));
  }, [id]);

  // 没有"当前版本"这种指针：最新一个已发布的版本就是可引用的那个。
  const usable = versions.find((version) => version.status === 'published')?.version;

  const columns: Column<Version>[] = [
    {
      key: 'version',
      label: t('datasets.colVersion'),
      render: (row) => (
        <>
          {`v${row.version}`}
          {row.version === usable && <span className="datasets-current">{t('datasets.usableNow')}</span>}
        </>
      ),
    },
    {
      key: 'status',
      label: t('datasets.colStatus'),
      render: (row) =>
        row.status === 'published' ? t('datasets.statusPublished') : t('datasets.statusDeprecated'),
    },
    {
      key: 'coverage',
      label: t('datasets.colCoverage'),
      render: (row) => `${row.date_from ?? '—'} → ${row.date_to ?? '—'}`,
    },
    { key: 'rows', label: t('datasets.colRows'), align: 'right', render: (row) => row.rows?.toLocaleString() ?? '—' },
    {
      key: 'published',
      label: t('datasets.colPublished'),
      render: (row) => (row.published_at ? row.published_at.slice(0, 10) : '—'),
    },
  ];

  return (
    <div className="datasets-page">
      <header className="datasets-header">
        <h1>{name}</h1>
        <p className="datasets-lead">
          <Link to="/datasets">{t('datasets.backToList')}</Link>
        </p>
      </header>

      <section className="datasets-section">
        <h2>{t('datasets.versionsTitle')}</h2>
        <p className="datasets-lead">{t('datasets.versionsHint')}</p>
        <DataTable<Version>
          columns={columns}
          rows={versions}
          rowKey={(row) => String(row.version)}
          empty={t('datasets.noVersions')}
          pageSize={10}
        />
      </section>
    </div>
  );
}
