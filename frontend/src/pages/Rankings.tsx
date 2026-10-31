import { useCallback, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { toast } from 'sonner';
import { apiFetch } from '../utils/api';
import { DataTable, type Column } from '../components/DataTable';
import './Rankings.scss';

type Source = {
  id: string;
  kind: string;
  display_name: string;
  description: string;
  method: string | null;
  row_count: number | null;
  date_from: string | null;
  date_to: string | null;
  dataset: { name: string | null; version: number | null };
  status: string;
  artifact_sha256: string;
  validation?: { ok?: boolean };
};

type RankRow = { ts_code: string; score: number; rank: number };

type Method = {
  name: string;
  display_name: string;
  description: string;
  output_kind: string;
  params_schema: { properties?: Record<string, { default?: unknown; title?: string; description?: string }> };
};

function defaultsFor(method: Method): Record<string, string> {
  const values: Record<string, string> = {};
  Object.entries(method.params_schema.properties ?? {}).forEach(([key, property]) => {
    values[key] = property.default == null ? '' : String(property.default);
  });
  return values;
}

function paramsPayload(values: Record<string, string>): Record<string, unknown> {
  const payload: Record<string, unknown> = {};
  Object.entries(values).forEach(([key, raw]) => {
    if (raw === '') return;
    const asNumber = Number(raw);
    payload[key] = Number.isNaN(asNumber) ? raw : asNumber;
  });
  return payload;
}

export function Rankings() {
  const { t } = useTranslation();
  const [sources, setSources] = useState<Source[]>([]);
  const [selected, setSelected] = useState<string>('');
  const [day, setDay] = useState<string>('');
  const [rows, setRows] = useState<RankRow[]>([]);
  // Generating a source happens here rather than on a separate "analyses" page: the page that owns the
  // output owns the button that produces it.
  const [methods, setMethods] = useState<Method[]>([]);
  const [methodName, setMethodName] = useState('');
  const [values, setValues] = useState<Record<string, string>>({});
  const [sourceName, setSourceName] = useState('');
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      const [res, methodRes] = await Promise.all([
        apiFetch<{ sources: Source[] }>('/api/rankings'),
        apiFetch<{ methods: Method[] }>('/api/analyses'),
      ]);
      setSources(res.sources);
      setSelected((current) => current || res.sources[0]?.id || '');
      const scoreTables = methodRes.methods.filter((item) => item.output_kind === 'score_table');
      setMethods(scoreTables);
      setMethodName((current) => current || scoreTables[0]?.name || '');
    } catch {
      toast.error(t('rankings.loadFailed'));
    }
  }, [t]);

  const method = methods.find((item) => item.name === methodName);

  useEffect(() => {
    setValues(method ? defaultsFor(method) : {});
  }, [method]);

  async function onGenerate() {
    if (!method) return;
    setBusy(true);
    try {
      await apiFetch(`/api/analyses/${method.name}/runs`, {
        method: 'POST',
        body: JSON.stringify({
          params: paramsPayload(values),
          source_id: sourceName || undefined,
          display_name: sourceName || undefined,
        }),
      });
      toast.success(t('rankings.started'));
      setSourceName('');
      await load();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : t('rankings.runFailed'));
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    void load();
  }, [load]);

  const preview = useCallback(async () => {
    if (!selected) return;
    const query = day ? `?day=${day}&limit=20` : '?limit=20';
    try {
      const res = await apiFetch<{ rows: RankRow[] }>(`/api/rankings/${selected}/preview${query}`);
      setRows(res.rows);
    } catch (error) {
      setRows([]);
      toast.error(error instanceof Error ? error.message : t('rankings.previewFailed'));
    }
  }, [selected, day, t]);

  useEffect(() => {
    void preview();
  }, [preview]);

  const columns: Column<Source>[] = [
    { key: 'name', label: t('rankings.colName'), render: (row) => row.display_name },
    { key: 'kind', label: t('rankings.colKind'), render: (row) => row.kind },
    {
      key: 'coverage',
      label: t('rankings.colCoverage'),
      render: (row) => `${row.date_from ?? '—'} → ${row.date_to ?? '—'}`,
    },
    {
      key: 'dataset',
      label: t('rankings.colDataset'),
      render: (row) =>
        row.dataset?.name ? `${row.dataset.name} v${row.dataset.version ?? '?'}` : '—',
    },
    { key: 'rows', label: t('rankings.colRows'), render: (row) => row.row_count?.toLocaleString() ?? '—' },
    { key: 'status', label: t('rankings.colStatus'), render: (row) => row.status },
  ];

  const rankColumns: Column<RankRow>[] = [
    { key: 'rank', label: '#', render: (row) => row.rank },
    { key: 'code', label: t('rankings.colCode'), render: (row) => row.ts_code },
    { key: 'score', label: t('rankings.colScore'), render: (row) => row.score.toFixed(3) },
  ];

  return (
    <div className="rankings-page">
      <h1>{t('rankings.title')}</h1>
      <p className="rankings-subtitle">{t('rankings.subtitle')}</p>

      <DataTable<Source>
        columns={columns}
        rows={sources}
        rowKey={(row) => row.id}
        empty={t('rankings.empty')}
        pageSize={10}
      />

      <div className="rankings-generate">
        <h2>{t('rankings.generate')}</h2>
        <p className="rankings-hint">{t('rankings.generateHint')}</p>
        <div className="form-row">
          <label htmlFor="rankings-method">{t('rankings.method')}</label>
          <select id="rankings-method" value={methodName} onChange={(e) => setMethodName(e.target.value)}>
            {methods.map((item) => (
              <option key={item.name} value={item.name}>
                {item.display_name}
              </option>
            ))}
          </select>
        </div>
        {method && <p className="rankings-hint">{method.description}</p>}
        {method &&
          Object.entries(method.params_schema.properties ?? {}).map(([key, property]) => (
            <div className="form-row" key={key}>
              <label htmlFor={`gen-${key}`}>{property.title ?? key}</label>
              <input
                id={`gen-${key}`}
                value={values[key] ?? ''}
                onChange={(event) => setValues((prev) => ({ ...prev, [key]: event.target.value }))}
              />
            </div>
          ))}
        <div className="form-row">
          <label htmlFor="rankings-source-name">{t('rankings.sourceName')}</label>
          <input
            id="rankings-source-name"
            value={sourceName}
            onChange={(e) => setSourceName(e.target.value)}
            placeholder={t('rankings.sourceNamePlaceholder')}
          />
        </div>
        <button type="button" className="btn btn-primary" onClick={onGenerate} disabled={busy || !method}>
          {busy ? t('rankings.running') : t('rankings.generateAction')}
        </button>
      </div>

      <div className="rankings-preview">
        <div className="form-row">
          <label htmlFor="rankings-source">{t('rankings.source')}</label>
          <select
            id="rankings-source"
            value={selected}
            onChange={(event) => setSelected(event.target.value)}
          >
            {sources.map((source) => (
              <option key={source.id} value={source.id}>
                {source.display_name}
              </option>
            ))}
          </select>
        </div>
        <div className="form-row">
          <label htmlFor="rankings-day">{t('rankings.day')}</label>
          <input
            id="rankings-day"
            type="date"
            value={day}
            onChange={(event) => setDay(event.target.value)}
          />
        </div>
        <button type="button" className="btn btn-secondary" onClick={preview} disabled={!selected}>
          {t('rankings.preview')}
        </button>

        <DataTable<RankRow>
          columns={rankColumns}
          rows={rows}
          rowKey={(row) => row.ts_code}
          empty={t('rankings.previewEmpty')}
          pageSize={10}
        />
      </div>
    </div>
  );
}
