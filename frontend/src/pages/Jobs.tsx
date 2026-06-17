import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { apiFetch } from '../utils/api';

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

  return (
    <div className="page-card">
      <h1 className="page-title">{t('nav.jobs')}</h1>
      <table className="data-table">
        <thead>
          <tr>
            <th>{t('home.jobType')}</th>
            <th>{t('home.jobStatus')}</th>
            <th>{t('home.jobTime')}</th>
            <th>{t('quote.col.actions')}</th>
            <th>Error</th>
          </tr>
        </thead>
        <tbody>
          {jobs.map((job) => (
            <tr key={job.id}>
              <td>{formatJobType(job.type, t)}</td>
              <td>{job.status}</td>
              <td>{job.created_at?.slice(0, 19).replace('T', ' ') ?? ''}</td>
              <td>
                {job.type === 'simulation' && job.status === 'completed' && (
                  <Link to={`/simulation/results?job_id=${encodeURIComponent(job.id)}`}>
                    {t('simulation.viewResults')}
                  </Link>
                )}
              </td>
              <td>{job.error ?? ''}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
