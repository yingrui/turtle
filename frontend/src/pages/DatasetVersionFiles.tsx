import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, useParams } from 'react-router-dom';
import { apiFetch } from '../utils/api';
import { DataTable, type Column } from '../components/DataTable';
import './Datasets.scss';

type FileRow = { name: string; rows: number | null; description: string | null; bytes: number | null };

/** 第三层：这个版本里有哪些文件。 */
export function DatasetVersionFiles() {
  const { t } = useTranslation();
  const { id = '', version = '' } = useParams();
  const [files, setFiles] = useState<FileRow[]>([]);

  useEffect(() => {
    apiFetch<{ files: FileRow[] }>(`/api/datasets/${encodeURIComponent(id)}/versions/${version}/files`)
      .then((d) => setFiles(d.files ?? []))
      .catch(() => setFiles([]));
  }, [id, version]);

  const columns: Column<FileRow>[] = [
    { key: 'name', label: t('datasets.colFile'), render: (row) => row.name },
    { key: 'rows', label: t('datasets.colRows'), align: 'right', render: (row) => row.rows?.toLocaleString() ?? '—' },
    { key: 'desc', label: t('datasets.colFileDesc'), render: (row) => row.description ?? '—' },
  ];

  return (
    <div className="datasets-page">
      <header className="datasets-header">
        <h1>{`${t('datasets.filesTitle')} · v${version}`}</h1>
        <p className="datasets-lead">
          <Link to={`/datasets/${id}`}>{t('datasets.backToVersions')}</Link>
        </p>
      </header>
      <DataTable<FileRow>
        columns={columns}
        rows={files}
        rowKey={(row) => row.name}
        empty={t('datasets.noFiles')}
        pageSize={50}
      />
    </div>
  );
}
