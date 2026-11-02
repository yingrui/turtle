import { useCallback, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { toast } from 'sonner';
import { apiFetch } from '../utils/api';
import { DataTable, type Column } from '../components/DataTable';
import './Analyses.scss';

type Property = {
  type?: string;
  format?: string;
  enum?: string[];
  items?: { type?: string };
  default?: unknown;
  description?: string;
  title?: string;
};

type ParamsSchema = { properties?: Record<string, Property>; required?: string[] };

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
    if (raw.startsWith('[') || raw === 'true' || raw === 'false') {
      try {
        payload[key] = JSON.parse(raw);
      } catch {
        payload[key] = raw;
      }
      return;
    }
    const asNumber = Number(raw);
    payload[key] = Number.isNaN(asNumber) || raw.trim() === '' ? raw : asNumber;
  });
  return payload;
}

const LABEL_CHOICES = [
  { value: 'benchmark', label: '跑赢基准（benchmark）' },
  { value: 'relative', label: '横截面相对排名（relative）' },
  { value: 'absolute', label: '绝对收益为正（absolute）' },
];

/**
 * 一个参数一个控件：日期用日期选择器、名单用多选、枚举用下拉、开关用复选框。
 * 之前全部渲染成文本框，用户得手打 "2025-07-01"、"["mom_20d"]" 这种内容。
 */
function Field({
  name,
  property,
  value,
  onChange,
  factors,
  benchmarks,
}: {
  name: string;
  property: Property;
  value: string;
  onChange: (next: string) => void;
  factors: string[];
  benchmarks: { ts_code: string; name: string }[];
}) {
  const label = property.title ?? name;
  const hint = property.description;
  const id = `param-${name}`;

  const hintNode = hint ? (
    <span id={`${id}-hint`} className="analyses-hint">
      {hint}
    </span>
  ) : null;
  const describedBy = hint ? `${id}-hint` : undefined;

  if (property.format === 'date') {
    return (
      <div className="form-row">
        <label htmlFor={id}>{label}</label>
        <input id={id} type="date" value={value} onChange={(e) => onChange(e.target.value)} aria-describedby={describedBy} />
        {hintNode}
      </div>
    );
  }

  if (property.type === 'array') {
    const selected = value ? (JSON.parse(value) as string[]) : [];
    const options = name === 'factors' ? factors : [];
    const toggle = (code: string) =>
      onChange(JSON.stringify(selected.includes(code) ? selected.filter((c) => c !== code) : [...selected, code]));
    return (
      <fieldset className="analyses-multi" aria-describedby={describedBy}>
        <legend>{label}</legend>
        {options.map((code) => (
          <label key={code}>
            <input type="checkbox" checked={selected.includes(code)} onChange={() => toggle(code)} />
            {code}
          </label>
        ))}
        {hintNode}
      </fieldset>
    );
  }

  if (property.type === 'boolean') {
    return (
      <label className="analyses-toggle" htmlFor={id}>
        <input
          id={id}
          type="checkbox"
          checked={value === 'true'}
          onChange={(e) => onChange(String(e.target.checked))}
          aria-describedby={describedBy}
        />
        {label}
        {hintNode}
      </label>
    );
  }

  if (name === 'benchmark') {
    return (
      <div className="form-row">
        <label htmlFor={id}>{label}</label>
        <select id={id} value={value} onChange={(e) => onChange(e.target.value)} aria-describedby={describedBy}>
          {benchmarks.map((item) => (
            <option key={item.ts_code} value={item.ts_code}>
              {item.name}
            </option>
          ))}
        </select>
        {hintNode}
      </div>
    );
  }

  if (name === 'label') {
    return (
      <div className="form-row">
        <label htmlFor={id}>{label}</label>
        <select id={id} value={value} onChange={(e) => onChange(e.target.value)} aria-describedby={describedBy}>
          {LABEL_CHOICES.map((choice) => (
            <option key={choice.value} value={choice.value}>
              {choice.label}
            </option>
          ))}
        </select>
        {hintNode}
      </div>
    );
  }

  if (property.enum) {
    return (
      <div className="form-row">
        <label htmlFor={id}>{label}</label>
        <select id={id} value={value} onChange={(e) => onChange(e.target.value)} aria-describedby={describedBy}>
          {property.enum.map((option) => (
            <option key={option} value={option}>
              {option}
            </option>
          ))}
        </select>
        {hintNode}
      </div>
    );
  }

  return (
    <div className="form-row">
      <label htmlFor={id}>{label}</label>
      <input id={id} value={value} onChange={(e) => onChange(e.target.value)} aria-describedby={describedBy} />
      {hintNode}
    </div>
  );
}

export function Analyses({
  embedded = false,
  only,
}: { embedded?: boolean; only?: 'dataset' | 'model' | 'score_table' } = {}) {
  const { t } = useTranslation();
  const [methods, setMethods] = useState<Method[]>([]);
  const [runs, setRuns] = useState<Run[]>([]);
  const [selected, setSelected] = useState<string>('');
  const [values, setValues] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const [factorOptions, setFactorOptions] = useState<string[]>([]);
  const [benchmarkOptions, setBenchmarkOptions] = useState<{ ts_code: string; name: string }[]>([]);

  const load = useCallback(async () => {
    try {
      const [methodRes, runRes] = await Promise.all([
        apiFetch<{ methods: Method[] }>('/api/analyses'),
        apiFetch<{ runs: Run[] }>('/api/analyses/runs'),
      ]);
      // Only real analyses: a control basket is declared where controls are, not here.
      const analyses = methodRes.methods.filter(
        (item) => item.family !== 'control' && (!only || item.output_kind === only),
      );
      setMethods(analyses);
      setRuns(runRes.runs);
      const first = methodRes.methods.find(
        (item) => item.family !== 'control' && (!only || item.output_kind === only),
      );
      setSelected((current) => current || first?.name || '');
    } catch {
      toast.error(t('analyses.loadFailed'));
    }
  }, [t, only]);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    apiFetch<{ factors: { code: string }[] }>('/api/factors')
      .then((d) => setFactorOptions((d.factors ?? []).map((f) => f.code)))
      .catch(() => setFactorOptions([]));
    apiFetch<{ indexes: { ts_code: string; name: string }[] }>('/api/indexes')
      .then((d) => setBenchmarkOptions((d.indexes ?? []).slice(0, 8)))
      .catch(() => setBenchmarkOptions([]));
  }, []);

  const method = methods.find((item) => item.name === selected);

  useEffect(() => {
    setValues(method ? defaultsFor(method.params_schema) : {});
  }, [method]);

  async function onRun() {
    if (!method) return;
    setBusy(true);
    try {
      // 语义是"创建一个模型/一次导出"，不是"调一个方法"。
      const endpoint = method.output_kind === 'dataset' ? '/api/datasets/build' : '/api/rankings';
      await apiFetch(endpoint, {
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
            <Field
              key={key}
              name={key}
              property={property}
              value={values[key] ?? ''}
              onChange={(next) => setValues((prev) => ({ ...prev, [key]: next }))}
              factors={factorOptions}
              benchmarks={benchmarkOptions}
            />
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
      </details>
    </div>
  );
}
