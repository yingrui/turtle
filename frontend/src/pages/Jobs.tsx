import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { apiFetch } from '../utils/api';
import { DataTable, type Column } from '../components/DataTable';

type Job = {
  id: string;
  type: string;
  status: string;
  created_at: string | null;
  error: string | null;
};

const LEGACY_TYPES = new Set(['data_sync', 'calendar_sync']);

function formatJobType(type: string, t: (k: string) => string) {
  if (LEGACY_TYPES.has(type)) return `${type} (${t('jobs.legacy')})`;
  return type;
}

export function Jobs() {
  const { t } = useTranslation();
  const [jobs, setJobs] = useState<Job[]>([]);

  useEffect(() => {
    apiFetch<{ jobs: Job[] }>('/api/jobs').then((d) => setJobs(d.jobs));
  }, []);

  const columns: Column<Job>[] = [
    {
      key: 'type',
      label: t('home.jobType'),
      sortable: true,
      sortValue: (job) => formatJobType(job.type, t),
      render: (job) => formatJobType(job.type, t),
    },
    {
      key: 'status',
      label: t('home.jobStatus'),
      sortable: true,
      sortValue: (job) => job.status,
      render: (job) => job.status,
    },
    {
      key: 'created_at',
      label: t('home.jobTime'),
      sortable: true,
      sortValue: (job) => job.created_at ?? '',
      render: (job) => job.created_at?.slice(0, 19).replace('T', ' ') ?? '',
    },
    {
      key: 'actions',
      label: t('quote.col.actions'),
      render: (job) =>
        job.type === 'simulation' && job.status === 'completed' ? (
          <Link to={`/simulation/results?job_id=${encodeURIComponent(job.id)}`}>
            {t('simulation.viewResults')}
          </Link>
        ) : null,
    },
    {
      key: 'error',
      label: 'Error',
      render: (job) => job.error ?? '',
    },
  ];

  return (
    <div className="page-card">
      <h1 className="page-title">{t('nav.jobs')}</h1>
      <DataTable
        pageSize={25}
        columns={columns}
        rows={jobs}
        rowKey={(job) => job.id}
        empty={t('home.noJobs')}
      />
    </div>
  );
}
