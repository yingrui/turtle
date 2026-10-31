import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, useSearchParams } from 'react-router-dom';
import { toast } from 'sonner';
import { apiFetch } from '../utils/api';
import { DataTable, type Column } from '../components/DataTable';
import { useJobPoll } from '../hooks/useJobPoll';
import './Simulation.scss';

type RankingSource = { id: string; display_name: string; kind: string; date_from: string | null; date_to: string | null };
type Strategy = { name: string; display_name: string; description: string };

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
  // Two ways to run: the classic signal backtest on the portfolio's own watchlist, or a model-driven
  // run whose pool comes from a published ranking source and whose trades follow a registered strategy.
  const [mode, setMode] = useState<'signal' | 'model'>('signal');
  const [sources, setSources] = useState<RankingSource[]>([]);
  const [sourceId, setSourceId] = useState('');
  const [strategies, setStrategies] = useState<Strategy[]>([]);
  const [strategyName, setStrategyName] = useState('pool_entry');
  const [retrain, setRetrain] = useState<'monthly' | 'weekly' | 'none'>('none');
  const [runName, setRunName] = useState('');
  const [jobId, setJobId] = useState<string | null>(searchParams.get('job_id'));
  const job = useJobPoll(jobId);
  type RunRow = {
    id: string;
    name: string | null;
    mode?: string | null;
    started_at: string | null;
    finished_at: string | null;
    window_start?: string | null;
    window_end?: string | null;
    return_rate_pct?: number | null;
    trade_count?: number | null;
  };
  const [runs, setRuns] = useState<RunRow[]>([]);
  // Running a backtest and reading past ones are different jobs; putting them side by side made the
  // page hard to use, so they are two views of the same route.
  const [view, setView] = useState<'run' | 'history'>('run');

  useEffect(() => {
    apiFetch<{ runs: RunRow[] }>('/api/simulations')
      .then((d) => setRuns(d.runs ?? []))
      .catch(() => setRuns([]));
  }, [job?.status]);

  useEffect(() => {
    const fromUrl = searchParams.get('job_id');
    if (fromUrl) setJobId(fromUrl);
  }, [searchParams]);

  useEffect(() => {
    apiFetch<{ portfolios: string[] }>('/api/portfolios')
      .then((d) => {
        setPortfolios(d.portfolios);
        // `?portfolio=` lets the portfolio page hand a run over with its portfolio preselected.
        const fromUrl = searchParams.get('portfolio');
        if (fromUrl && d.portfolios.includes(fromUrl)) setPortfolio(fromUrl);
        else if (d.portfolios.length) setPortfolio(d.portfolios[0]);
      })
      .catch(() => toast.error('Failed to load portfolios'));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    apiFetch<{ sources: RankingSource[] }>('/api/rankings')
      .then((d) => {
        setSources(d.sources ?? []);
        setSourceId((current) => current || d.sources?.[0]?.id || '');
      })
      .catch(() => setSources([]));
    apiFetch<{ strategies: Strategy[] }>('/api/strategies')
      .then((d) => setStrategies(d.strategies ?? []))
      .catch(() => setStrategies([]));
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
    if (mode === 'signal' && !selectedPolicies.length) {
      toast.error('Select at least one policy');
      return;
    }
    try {
      const body =
        mode === 'model'
          ? {
              type: 'simulation',
              mode: 'model',
              portfolio,
              start_date: startDate,
              end_date: endDate,
              buy_rule: strategyName,
              ranking_source_id: sourceId,
              retrain,
              name: runName || undefined,
              description: runName || undefined,
            }
          : { type: 'simulation', portfolio, start_date: startDate, end_date: endDate, policy_ids: selectedPolicies };
      const res = await apiFetch<{ id: string }>('/api/jobs', {
        method: 'POST',
        body: JSON.stringify(body),
      });
      setJobId(res.id);
      setSearchParams({ job_id: res.id }, { replace: true });
      toast.success(t('simulation.started'));
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to start simulation');
    }
  }

  const policyCount = config?.policies?.length ?? 0;

  const runColumns: Column<RunRow>[] = [
    {
      key: 'name',
      label: t('simulation.colRun'),
      render: (row) => (
        <Link to={`/simulation/results?run_id=${encodeURIComponent(row.id)}`}>
          {row.name || row.id.slice(0, 8)}
        </Link>
      ),
    },
    { key: 'mode', label: t('simulation.colMode'), render: (row) => row.mode ?? 'signal' },
    {
      key: 'window',
      label: t('simulation.colWindow'),
      render: (row) =>
        row.window_start && row.window_end ? `${row.window_start} → ${row.window_end}` : '—',
    },
    {
      key: 'trades',
      label: t('simulation.colTrades'),
      render: (row) => (row.trade_count == null ? '—' : row.trade_count.toLocaleString()),
    },
    {
      key: 'return',
      label: t('simulation.colReturn'),
      render: (row) =>
        row.return_rate_pct == null ? '—' : `${row.return_rate_pct.toFixed(2)}%`,
    },
    {
      key: 'status',
      label: t('simulation.colStatus'),
      render: (row) => (
        <span className={row.finished_at ? 'simulation-run-done' : 'simulation-run-open'}>
          {row.finished_at ? t('simulation.runDone') : t('simulation.runOpen')}
        </span>
      ),
    },
  ];

  return (
    <div className="simulation-page">
      <div className="simulation-tabs" role="tablist">
        <button
          type="button"
          role="tab"
          aria-selected={view === 'run'}
          className={`btn ${view === 'run' ? 'btn-primary' : 'btn-secondary'}`}
          onClick={() => setView('run')}
        >
          {t('simulation.tabRun')}
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={view === 'history'}
          className={`btn ${view === 'history' ? 'btn-primary' : 'btn-secondary'}`}
          onClick={() => setView('history')}
        >
          {t('simulation.tabHistory')}
        </button>
      </div>

      {view === 'history' && (
        <DataTable<RunRow>
          columns={runColumns}
          rows={runs}
          rowKey={(row) => row.id}
          empty={t('simulation.noRuns')}
          pageSize={15}
        />
      )}

      <div className={view === 'run' ? 'simulation-config' : 'simulation-config simulation-hidden'}>
      <div className="form-row field-wide">
        <label htmlFor="portfolio">Portfolio</label>
        <select id="portfolio" value={portfolio} onChange={(e) => setPortfolio(e.target.value)}>
          {portfolios.map((p) => (
            <option key={p} value={p}>{p}</option>
          ))}
        </select>
      </div>
      <div className="form-row field-wide">
        <label htmlFor="run-mode">{t('simulation.mode')}</label>
        <select id="run-mode" value={mode} onChange={(e) => setMode(e.target.value as 'signal' | 'model')}>
          <option value="signal">{t('simulation.modeSignal')}</option>
          <option value="model">{t('simulation.modeModel')}</option>
        </select>
      </div>
      {mode === 'model' && (
        <div>
          <div className="form-row field-wide">
            <label htmlFor="ranking-source">{t('simulation.poolSource')}</label>
            <select id="ranking-source" value={sourceId} onChange={(e) => setSourceId(e.target.value)}>
              {sources.map((source) => (
                <option key={source.id} value={source.id}>
                  {source.display_name} · {source.kind}
                </option>
              ))}
            </select>
          </div>
          <div className="form-row field-wide">
            <label htmlFor="strategy">{t('simulation.strategy')}</label>
            <select id="strategy" value={strategyName} onChange={(e) => setStrategyName(e.target.value)}>
              {strategies.map((strategy) => (
                <option key={strategy.name} value={strategy.name}>
                  {strategy.display_name}
                </option>
              ))}
            </select>
          </div>
          <div className="form-row field-wide">
            <label htmlFor="retrain">{t('simulation.retrain')}</label>
            <select id="retrain" value={retrain} onChange={(e) => setRetrain(e.target.value as 'monthly' | 'weekly' | 'none')}>
              <option value="none">{t('simulation.retrainNone')}</option>
              <option value="monthly">{t('simulation.retrainMonthly')}</option>
              <option value="weekly">{t('simulation.retrainWeekly')}</option>
            </select>
          </div>
          <div className="form-row field-wide">
            <label htmlFor="run-name">{t('simulation.runName')}</label>
            <input id="run-name" value={runName} onChange={(e) => setRunName(e.target.value)} />
          </div>
        </div>
      )}
      <div className="toolbar">
        <div className="form-row field-medium">
          <label htmlFor="start-date">Start date</label>
          <input id="start-date" type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} />
        </div>
        <div className="form-row field-medium">
          <label htmlFor="end-date">End date</label>
          <input id="end-date" type="date" value={endDate} onChange={(e) => setEndDate(e.target.value)} />
        </div>
      </div>
      {mode === 'signal' && policyCount > 0 && (
        <div>
          <p className="text-hint mb-2">
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
          <p className="mt-4">
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
      </div>
    </div>
  );
}
