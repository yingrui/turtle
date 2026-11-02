import { useCallback, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { toast } from 'sonner';
import { apiFetch } from '../utils/api';
import { DataTable, type Column } from '../components/DataTable';
import './Analyses.scss';

type ParamsSchema = {
  properties?: Record<string, { type?: string; default?: unknown; description?: string; title?: string }>;
  required?: string[];
};

type Method = {
  name: string;
  display_name: string;
  description: string;
  output_kind: string;
  /** `analysis` computes scores from data; `control` builds a basket with no model behind it. */
  family: string;
  params_schema: ParamsSchema;
};

type Run = {
  id: string;
  method: string;
  status: string;
  source_id: string | null;
  error: string | null;
  created_at: string | null;
};

function defaultsFor(schema: ParamsSchema): Record<string, string> {
  const values: Record<string, string> = {};
  Object.entries(schema.properties ?? {}).forEach(([key, property]) => {
    values[key] = property.default == null ? '' : String(property.default);
  });
  return values;
}

function paramsPayload(values: Record<string, string>): Record<string, unknown> {
  const payload: Record<string, unknown> = {};
  Object.entries(values).forEach(([key, raw]) => {
    if (raw === '') return;
    const asNumber = Number(raw);
    payload[key] = Number.isNaN(asNumber) || raw.trim() === '' ? raw : asNumber;
  });
  return payload;
}

export function Analyses({ embedded = false }: { embedded?: boolean } = {}) {
  const { t } = useTranslation();
  const [methods, setMethods] = useState<Method[]>([]);
  const [runs, setRuns] = useState<Run[]>([]);
  const [selected, setSelected] = useState<string>('');
  const [values, setValues] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      const [methodRes, runRes] = await Promise.all([
        apiFetch<{ methods: Method[] }>('/api/analyses'),
        apiFetch<{ runs: Run[] }>('/api/analyses/runs'),
      ]);
      // Only real analyses: a control basket is declared where controls are, not here.
      const analyses = methodRes.methods.filter((item) => item.family !== 'control');
      setMethods(analyses);
      setRuns(runRes.runs);
      setSelected((current) => current || methodRes.methods.find((item) => item.family !== 'control')?.name || '');
    } catch {
      toast.error(t('analyses.loadFailed'));
    }
  }, [t]);

  useEffect(() => {
    void load();
  }, [load]);

  const method = methods.find((item) => item.name === selected);

  useEffect(() => {
    setValues(method ? defaultsFor(method.params_schema) : {});
  }, [method]);

  async function onRun() {
    if (!method) return;
    setBusy(true);
    try {
      await apiFetch(`/api/analyses/${method.name}/runs`, {
        method: 'POST',
        body: JSON.stringify({ params: paramsPayload(values) }),
      });
      toast.success(t('analyses.started'));
      await load();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : t('analyses.runFailed'));
    } finally {
      setBusy(false);
    }
  }

  const columns: Column<Run>[] = [
    { key: 'method', label: t('analyses.colMethod'), render: (row) => row.method },
    { key: 'status', label: t('analyses.colStatus'), render: (row) => row.status },
    { key: 'source', label: t('analyses.colSource'), render: (row) => row.source_id ?? '—' },
    {
      key: 'created',
      label: t('analyses.colCreated'),
      render: (row) => (row.created_at ? row.created_at.slice(0, 19).replace('T', ' ') : '—'),
    },
    { key: 'error', label: t('analyses.colError'), render: (row) => row.error ?? '—' },
  ];

  return (
    <div className={embedded ? 'analyses-body' : 'analyses-page'}>
      {!embedded && (
        <>
          <h1>{t('analyses.title')}</h1>
          <p className="analyses-subtitle">{t('analyses.subtitle')}</p>
        </>
      )}

      <div className="analyses-form">
        <div className="form-row">
          <label htmlFor="analysis-method">{t('analyses.method')}</label>
          <select
            id="analysis-method"
            value={selected}
            onChange={(event) => setSelected(event.target.value)}
          >
            {methods.map((item) => (
              <option key={item.name} value={item.name}>
                {item.display_name}
              </option>
            ))}
          </select>
        </div>
        {method && <p className="analyses-hint">{method.description}</p>}

        {method &&
          Object.entries(method.params_schema.properties ?? {}).map(([key, property]) => (
            <div className="form-row" key={key}>
              <label htmlFor={`param-${key}`}>{property.title ?? key}</label>
              <input
                id={`param-${key}`}
                value={values[key] ?? ''}
                onChange={(event) =>
                  setValues((prev) => ({ ...prev, [key]: event.target.value }))
                }
                aria-describedby={property.description ? `param-${key}-hint` : undefined}
              />
              {property.description && (
                <span id={`param-${key}-hint`} className="analyses-hint">
                  {property.description}
                </span>
              )}
            </div>
          ))}

        <button type="button" className="btn btn-primary" onClick={onRun} disabled={busy || !method}>
          {busy ? t('analyses.running') : t('analyses.run')}
        </button>
      </div>

      <details className="analyses-history">
        <summary>{t('analyses.history')}</summary>
      <DataTable<Run>
        columns={columns}
        rows={runs}
        rowKey={(row) => row.id}
        empty={t('analyses.empty')}
        pageSize={10}
      />
    </div>
  );
}
