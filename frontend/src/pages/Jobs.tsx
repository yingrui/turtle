import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { apiFetch } from '../utils/api';

type Job = {
  id: string;
  type: string;
  status: string;
  created_at: string | null;
  error: string | null;
};

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
            <th>Type</th>
            <th>Status</th>
            <th>Created</th>
            <th>Error</th>
          </tr>
        </thead>
        <tbody>
          {jobs.map((job) => (
            <tr key={job.id}>
              <td>{job.type}</td>
              <td>{job.status}</td>
              <td>{job.created_at?.slice(0, 19).replace('T', ' ') ?? ''}</td>
              <td>{job.error ?? ''}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
