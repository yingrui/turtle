import { useCallback, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, useParams } from 'react-router-dom';
import { apiFetch } from '../utils/api';
import './Methods.scss';

type Source = {
  id: string;
  kind: string;
  display_name: string;
  description: string;
  method: string | null;
  params: Record<string, unknown>;
  row_count: number | null;
  date_from: string | null;
  date_to: string | null;
  dataset: { name: string | null; version: number | null };
  label: Record<string, unknown>;
  status: string;
  artifact_sha256: string;
};

type RankRow = { ts_code: string; score: number; rank: number };

/** 第二层：这一个模型是什么、它某天选了什么。只讲一个模型。 */
export function MethodDetail() {
  const { t } = useTranslation();
  const { id = '' } = useParams();
  const [source, setSource] = useState<Source | null>(null);
  const [day, setDay] = useState('');
  const [rows, setRows] = useState<RankRow[]>([]);

  useEffect(() => {
    apiFetch<Source>(`/api/rankings/${encodeURIComponent(id)}`)
      .then((d) => {
        setSource(d);
        // 老数据的覆盖区间可能只有 "2025-07" 这种月份，日期输入框不接受，退回到今天。
        const candidate = d.date_to ?? '';
        setDay(/^\d{4}-\d{2}-\d{2}$/.test(candidate) ? candidate : new Date().toISOString().slice(0, 10));
      })
      .catch(() => setSource(null));
  }, [id]);

  async function onDelete() {
    if (!window.confirm(t('methods.deleteConfirm'))) return;
    try {
      await apiFetch(`/api/rankings/${encodeURIComponent(id)}`, { method: 'DELETE' });
      window.location.href = '/methods';
    } catch (error) {
      window.alert(error instanceof Error ? error.message : String(error));
    }
  }

  const preview = useCallback(async () => {
    if (!id) return;
    try {
      const query = day ? `?day=${encodeURIComponent(day)}&limit=20` : '?limit=20';
      const d = await apiFetch<{ rows: RankRow[] }>(`/api/rankings/${encodeURIComponent(id)}/preview${query}`);
      setRows(d.rows ?? []);
    } catch {
      setRows([]);
    }
  }, [id, day]);

  useEffect(() => {
    void preview();
  }, [preview]);

  if (!source) {
    return (
      <div className="methods-page">
        <p className="methods-hint">{t('methods.notFound')}</p>
        <Link to="/methods">{t('methods.backToList')}</Link>
      </div>
    );
  }

  return (
    <div className="methods-page">
      <header className="methods-header">
        <h1>{source.display_name}</h1>
        <p className="methods-hint">
          <Link to="/methods">{t('methods.backToList')}</Link>
        </p>
        <button type="button" className="btn btn-secondary" onClick={onDelete}>
          {t('methods.delete')}
        </button>
      </header>

      <section className="methods-section">
        <dl className="methods-facts">
          <dt>{t('methods.factAlgorithm')}</dt>
          <dd>{source.method ?? '—'}</dd>
          <dt>{t('methods.factCoverage')}</dt>
          <dd>{`${source.date_from ?? '—'} → ${source.date_to ?? '—'}`}</dd>
          <dt>{t('methods.factRows')}</dt>
          <dd>
            {source.kind === 'model'
              ? t('rankings.onTheFly', { periods: (source.params?.periods as unknown[] | undefined)?.length ?? '—' })
              : t('methods.rowsExplain', { rows: source.row_count?.toLocaleString() ?? '—' })}
          </dd>
          <dt>{t('methods.factDataset')}</dt>
          <dd>{source.dataset?.name ? `${source.dataset.name} v${source.dataset.version ?? '?'}` : '—'}</dd>
          <dt>{t('methods.factParams')}</dt>
          <dd>{JSON.stringify(source.params ?? {})}</dd>
        </dl>
      </section>

      <section className="methods-section">
        <h2>{t('methods.detailPreview')}</h2>
        <div className="form-row field-medium">
          <label htmlFor="md-day">{t('methods.pickDay')}</label>
          <input id="md-day" type="date" value={day} onChange={(e) => setDay(e.target.value)} />
        </div>
        {rows.length === 0 ? (
          <p className="methods-hint">{t('methods.previewEmpty')}</p>
        ) : (
          <ol className="methods-ranks">
            {rows.map((row) => (
              <li key={row.ts_code} className="methods-rank">
                <span className="methods-rank__no">{row.rank}</span>
                <span className="methods-rank__code">{row.ts_code}</span>
                <span className="methods-rank__bar">
                  <span
                    className="methods-rank__fill"
                    style={
                      {
                        '--fill': `${((rows[0].score - row.score) / Math.max(1e-9, rows[0].score - rows[rows.length - 1].score)) * 100}%`,
                      } as React.CSSProperties
                    }
                  />
                </span>
                <span className="methods-rank__score">{row.score.toFixed(4)}</span>
              </li>
            ))}
          </ol>
        )}
      </section>
    </div>
  );
}
