import { useEffect, useState } from 'react';
import { apiFetch } from '../utils/api';

type Job = {
  id: string;
  status: string;
  log: string;
  error: string | null;
  result: string | null;
};

export function useJobPoll(jobId: string | null) {
  const [job, setJob] = useState<Job | null>(null);

  useEffect(() => {
    if (!jobId) return;
    let active = true;
    const poll = async () => {
      const j = await apiFetch<Job>(`/api/jobs/${jobId}`);
      if (!active) return;
      setJob(j);
      if (j.status === 'pending' || j.status === 'running') {
        setTimeout(poll, 2000);
      }
    };
    poll();
    return () => {
      active = false;
    };
  }, [jobId]);

  return job;
}
