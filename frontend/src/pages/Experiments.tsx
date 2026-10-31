import { useCallback, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { toast } from 'sonner';
import { apiFetch } from '../utils/api';
import { DataTable, type Column } from '../components/DataTable';
import './Experiments.scss';

type ExperimentListItem = {
  id: string;
  question: string;
  status: string;
  strategy: string;
  window: [string | null, string | null];
  variants: number;
  controls: number;
  verdict: string | null;
};

type Cell = {
  variant: string;
  is_control: boolean;
  run_id: string | null;
  status: string;
  excess_pct: number | null;
  trades: number | null;
  sigma?: number;
};

type Detail = {
  id: string;
  question: string;
  status: string;
  strategy: string;
  window: [string | null, string | null];
  cells: Cell[];
  controls: { mean: number; sd: number; n: number } | null;
  conclusion: Record<string, string>;
};

type Source = { id: string; display_name: string; kind: string };

export function Experiments() {
  const { t } = useTranslation();
  const [list, setList] = useState<ExperimentListItem[]>([]);
  const [detail, setDetail] = useState<Detail | null>(null);
  const [sources, setSources] = useState<Source[]>([]);
  const [question, setQuestion] = useState('');
  const [kill, setKill] = useState('');
  const [start, setStart] = useState('2025-07-01');
  const [end, setEnd] = useState(new Date().toISOString().slice(0, 10));
  const [variantIds, setVariantIds] = useState<string[]>([]);
  const [controlIds, setControlIds] = useState<string[]>([]);

  const load = useCallback(async () => {
    try {
      const [experiments, sourceRes] = await Promise.all([
        apiFetch<{ experiments: ExperimentListItem[] }>('/api/experiments'),
        apiFetch<{ sources: Source[] }>('/api/rankings'),
      ]);
      setList(experiments.experiments);
      setSources(sourceRes.sources);
    } catch {
      toast.error(t('experiments.loadFailed'));
    }
  }, [t]);

  useEffect(() => {
    void load();
  }, [load]);

  async function openDetail(id: string) {
    try {
      setDetail(await apiFetch<Detail>(`/api/experiments/${id}`));
    } catch {
      toast.error(t('experiments.detailFailed'));
    }
  }

  function toggle(id: string, current: string[], setValue: (next: string[]) => void) {
    setValue(current.includes(id) ? current.filter((item) => item !== id) : [...current, id]);
  }

  async function onExpand(id: string) {
    try {
      const res = await apiFetch<{ launched: { variant: string; job_id: string }[] }>(
        `/api/experiments/${id}/expand`,
        { method: 'POST', body: JSON.stringify({}) },
      );
      toast.success(t('experiments.expanded', { count: res.launched.length }));
      await openDetail(id);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : t('experiments.expandFailed'));
    }
  }

  async function onCreate() {
    if (!controlIds.length) {
      toast.error(t('experiments.controlsRequired'));
      return;
    }
    try {
      await apiFetch('/api/experiments', {
        method: 'POST',
        body: JSON.stringify({
          question,
          hypothesis: { kill },
          variants: variantIds.map((id) => ({ name: id, ranking_source_id: id })),
          controls: controlIds.map((id) => ({ name: id, ranking_source_id: id })),
          window_start: start,
          window_end: end,
          strategy: 'pool_entry',
          label: { kind: 'benchmark', horizon: 20 },
        }),
      });
      toast.success(t('experiments.created'));
      await load();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : t('experiments.createFailed'));
    }
  }

  const columns: Column<ExperimentListItem>[] = [
    {
      key: 'question',
      label: t('experiments.colQuestion'),
      render: (row) => (
        <button type="button" className="btn btn-link" onClick={() => openDetail(row.id)}>
          {row.question}
        </button>
      ),
    },
    { key: 'status', label: t('experiments.colStatus'), render: (row) => row.status },
    { key: 'strategy', label: t('experiments.colStrategy'), render: (row) => row.strategy },
    {
      key: 'window',
      label: t('experiments.colWindow'),
      render: (row) => `${row.window[0] ?? '—'} → ${row.window[1] ?? '—'}`,
    },
    {
      key: 'cells',
      label: t('experiments.colCells'),
      render: (row) => `${row.variants} / ${row.controls}`,
    },
    { key: 'verdict', label: t('experiments.colVerdict'), render: (row) => row.verdict ?? '—' },
  ];

  const cellColumns: Column<Cell>[] = [
    { key: 'variant', label: t('experiments.colVariant'), render: (row) => row.variant },
    {
      key: 'role',
      label: t('experiments.colRole'),
      render: (row) => (row.is_control ? t('experiments.control') : t('experiments.variant')),
    },
    { key: 'status', label: t('experiments.colRunStatus'), render: (row) => row.status },
    {
      key: 'excess',
      label: t('experiments.colExcess'),
      render: (row) => (row.excess_pct == null ? '—' : `${row.excess_pct.toFixed(2)}`),
    },
    {
      key: 'sigma',
      label: t('experiments.colSigma'),
      render: (row) => (row.sigma == null ? '—' : `${row.sigma.toFixed(2)}σ`),
    },
    { key: 'trades', label: t('experiments.colTrades'), render: (row) => row.trades ?? '—' },
  ];

  return (
    <div className="experiments-page">
      <h1>{t('experiments.title')}</h1>
      <p className="experiments-subtitle">{t('experiments.subtitle')}</p>

      <div className="experiments-form">
        <div className="form-row">
          <label htmlFor="exp-question">{t('experiments.question')}</label>
          <input id="exp-question" value={question} onChange={(e) => setQuestion(e.target.value)} />
        </div>
        <div className="form-row">
          <label htmlFor="exp-kill">{t('experiments.kill')}</label>
          <input id="exp-kill" value={kill} onChange={(e) => setKill(e.target.value)} />
        </div>
        <div className="toolbar">
          <div className="form-row field-medium">
            <label htmlFor="exp-start">{t('experiments.start')}</label>
            <input id="exp-start" type="date" value={start} onChange={(e) => setStart(e.target.value)} />
          </div>
          <div className="form-row field-medium">
            <label htmlFor="exp-end">{t('experiments.end')}</label>
            <input id="exp-end" type="date" value={end} onChange={(e) => setEnd(e.target.value)} />
          </div>
        </div>

        <fieldset className="experiments-picker">
          <legend>{t('experiments.variants')}</legend>
          {sources.map((source) => (
            <label key={`v-${source.id}`}>
              <input
                type="checkbox"
                checked={variantIds.includes(source.id)}
                onChange={() => toggle(source.id, variantIds, setVariantIds)}
              />
              {source.display_name}
            </label>
          ))}
        </fieldset>

        <fieldset className="experiments-picker">
          <legend>{t('experiments.controls')}</legend>
          {sources.map((source) => (
            <label key={`c-${source.id}`}>
              <input
                type="checkbox"
                checked={controlIds.includes(source.id)}
                onChange={() => toggle(source.id, controlIds, setControlIds)}
              />
              {source.display_name}
            </label>
          ))}
        </fieldset>

        <button type="button" className="btn btn-primary" onClick={onCreate} disabled={!question}>
          {t('experiments.create')}
        </button>
      </div>

      <DataTable<ExperimentListItem>
        columns={columns}
        rows={list}
        rowKey={(row) => row.id}
        empty={t('experiments.empty')}
        pageSize={10}
      />

      {detail && (
        <div className="experiments-detail">
          <h2>{detail.question}</h2>
          <div>
            <button type="button" className="btn btn-primary" onClick={() => onExpand(detail.id)}>
              {t('experiments.expand')}
            </button>
          </div>
          {detail.controls && (
            <p className="experiments-hint">
              {t('experiments.band', {
                n: detail.controls.n,
                mean: detail.controls.mean.toFixed(2),
                sd: detail.controls.sd.toFixed(2),
              })}
            </p>
          )}
          <DataTable<Cell>
            columns={cellColumns}
            rows={detail.cells}
            rowKey={(row) => row.variant}
            empty={t('experiments.noCells')}
            pageSize={10}
          />
        </div>
      )}
    </div>
  );
}
