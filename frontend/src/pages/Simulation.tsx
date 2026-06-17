import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, useSearchParams } from 'react-router-dom';
import { toast } from 'sonner';
import { apiFetch } from '../utils/api';
import { useJobPoll } from '../hooks/useJobPoll';

type PortfolioConfig = {
  policies?: unknown[];
  start_date?: string;
};

export function Simulation() {
  const { t } = useTranslation();
  const [searchParams, setSearchParams] = useSearchParams();
  const [portfolios, setPortfolios] = useState<string[]>([]);
  const [portfolio, setPortfolio] = useState('');
  const [config, setConfig] = useState<PortfolioConfig | null>(null);
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState(new Date().toISOString().slice(0, 10));
  const [selectedPolicies, setSelectedPolicies] = useState<number[]>([]);
  const [jobId, setJobId] = useState<string | null>(searchParams.get('job_id'));
  const job = useJobPoll(jobId);

  useEffect(() => {
    const fromUrl = searchParams.get('job_id');
    if (fromUrl) setJobId(fromUrl);
  }, [searchParams]);

  useEffect(() => {
    apiFetch<{ portfolios: string[] }>('/api/portfolios')
      .then((d) => {
        setPortfolios(d.portfolios);
        if (d.portfolios.length) setPortfolio(d.portfolios[0]);
      })
      .catch(() => toast.error('Failed to load portfolios'));
  }, []);

  useEffect(() => {
    if (!portfolio) return;
    apiFetch<PortfolioConfig>(`/api/portfolios/${portfolio}`)
      .then((cfg) => {
        setConfig(cfg);
        if (cfg.start_date) setStartDate(String(cfg.start_date).slice(0, 10));
        const n = cfg.policies?.length ?? 0;
        setSelectedPolicies(Array.from({ length: n }, (_, i) => i));
      })
      .catch(() => {});
  }, [portfolio]);

  function togglePolicy(id: number) {
    setSelectedPolicies((prev) =>
      prev.includes(id) ? prev.filter((p) => p !== id) : [...prev, id].sort((a, b) => a - b),
    );
  }

  async function onRun() {
    if (!selectedPolicies.length) {
      toast.error('Select at least one policy');
      return;
    }
    try {
      const res = await apiFetch<{ id: string }>('/api/jobs', {
        method: 'POST',
        body: JSON.stringify({
          type: 'simulation',
          portfolio,
          start_date: startDate,
          end_date: endDate,
          policy_ids: selectedPolicies,
        }),
      });
      setJobId(res.id);
      setSearchParams({ job_id: res.id }, { replace: true });
      toast.success(t('simulation.started'));
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to start simulation');
    }
  }

  const policyCount = config?.policies?.length ?? 0;

  return (
    <>
      <div className="form-row" style={{ maxWidth: 300 }}>
        <label htmlFor="portfolio">Portfolio</label>
        <select id="portfolio" value={portfolio} onChange={(e) => setPortfolio(e.target.value)}>
          {portfolios.map((p) => (
            <option key={p} value={p}>{p}</option>
          ))}
        </select>
      </div>
      <div style={{ display: 'flex', gap: 'var(--space-4)', flexWrap: 'wrap' }}>
        <div className="form-row" style={{ maxWidth: 200 }}>
          <label htmlFor="start-date">Start date</label>
          <input id="start-date" type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} />
        </div>
        <div className="form-row" style={{ maxWidth: 200 }}>
          <label htmlFor="end-date">End date</label>
          <input id="end-date" type="date" value={endDate} onChange={(e) => setEndDate(e.target.value)} />
        </div>
      </div>
      {policyCount > 0 && (
        <div>
          <p style={{ fontSize: 'var(--text-sm)', color: 'var(--color-text-muted)', marginBottom: 'var(--space-2)' }}>
            Policies to run ({selectedPolicies.length}/{policyCount})
          </p>
          <div className="policy-checkboxes">
            {Array.from({ length: policyCount }, (_, i) => (
              <label key={i}>
                <input type="checkbox" checked={selectedPolicies.includes(i)} onChange={() => togglePolicy(i)} />
                Policy {i}
              </label>
            ))}
          </div>
        </div>
      )}
      <button type="button" className="btn btn-primary" onClick={onRun} disabled={!portfolio || !startDate}>
        Run Simulation
      </button>
      {job && (
        <div>
          <p style={{ marginTop: 'var(--space-4)' }}>
            Status: <strong>{job.status}</strong>
          </p>
          {job.status === 'completed' && job.id && (
            <p>
              <Link to={`/simulation/results?job_id=${encodeURIComponent(job.id)}`}>
                {t('simulation.viewResults')} →
              </Link>
            </p>
          )}
          {job.error && <p className="error-banner">{job.error}</p>}
          {job.log && <pre className="log-panel">{job.log}</pre>}
        </div>
      )}
    </>
  );
}
