import { useCallback, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { toast } from 'sonner';
import { apiFetch } from '../utils/api';
import { DataTable, type Column } from '../components/DataTable';
import './Datasets.scss';

type Dataset = { id: string; name: string; kind: string; description: string | null };

/** 第一层：有哪些数据集。点一个进详情看版本。 */
export function Datasets() {
  const { t } = useTranslation();
  const [datasets, setDatasets] = useState<Dataset[]>([]);

  const load = useCallback(async () => {
    try {
      const res = await apiFetch<{ datasets: Dataset[] }>('/api/datasets');
      setDatasets(res.datasets ?? []);
    } catch {
      toast.error(t('datasets.loadFailed'));
    }
  }, [t]);

  useEffect(() => {
    void load();
  }, [load]);

  const columns: Column<Dataset>[] = [
    {
      key: 'name',
      label: t('datasets.colName'),
      render: (row) => <Link to={`/datasets/${row.id}`}>{row.name}</Link>,
    },
    { key: 'kind', label: t('datasets.colKind'), render: (row) => row.kind },
  ];

  return (
    <div className="datasets-page">
      <header className="datasets-header">
        <div className="datasets-head-row">
          <h1>{t('datasets.title')}</h1>
          <Link className="btn btn-primary" to="/datasets/new">
            {t('datasets.buildTitle')}
          </Link>
        </div>
        <p className="datasets-lead">{t('datasets.lead')}</p>
      </header>

      <DataTable<Dataset>
        columns={columns}
        rows={datasets}
        rowKey={(row) => row.id}
        empty={t('datasets.empty')}
        pageSize={20}
      />
    </div>
  );
}
