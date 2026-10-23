import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { toast } from 'sonner';
import { apiFetch } from '../utils/api';
import { DataTable, type Column } from '../components/DataTable';

export type Factor = {
  code: string;
  name: string;
  category: string;
  direction: 'positive' | 'negative' | 'neutral';
  unit: string | null;
  logic: string | null;
  formula: string | null;
  params: Record<string, unknown>;
  lookback_days: number | null;
  ic_ir: number | null;
  source_ref: string | null;
  is_computable: boolean;
  value_count: number;
  stock_count: number;
  first_date: string | null;
  last_date: string | null;
};

/** The catalogue: what factors exist, whether they can be computed, and how far they got. */
export function FactorList() {
  const { t } = useTranslation();
  const [factors, setFactors] = useState<Factor[]>([]);
  const [loading, setLoading] = useState(false);
  const [search, setSearch] = useState('');
  const [category, setCategory] = useState('');
  const [computableOnly, setComputableOnly] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const query = new URLSearchParams();
      if (computableOnly) query.set('computable', 'true');
      if (category) query.set('category', category);
      const data = await apiFetch<{ factors: Factor[] }>(`/api/factors?${query.toString()}`);
      setFactors(data.factors);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : t('factor.loadFailed'));
    } finally {
      setLoading(false);
    }
  }, [computableOnly, category, t]);

  useEffect(() => {
    load();
  }, [load]);

  const visible = useMemo(() => {
    const needle = search.trim().toLowerCase();
    if (!needle) return factors;
    return factors.filter(
      (f) =>
        f.code.toLowerCase().includes(needle) ||
        f.name.toLowerCase().includes(needle) ||
        (f.logic ?? '').toLowerCase().includes(needle),
    );
  }, [factors, search]);

  const categories = useMemo(
    () => Array.from(new Set(factors.map((f) => f.category))).sort(),
    [factors],
  );

  const columns: Column<Factor>[] = [
    {
      key: 'code',
      label: t('factor.col.code'),
      sortable: true,
      sortValue: (row) => row.code,
      render: (row) => (
        <span>
          <Link to={`/factor/${encodeURIComponent(row.code)}`}>
            <strong>{row.code}</strong>
          </Link>
          {row.is_computable ? null : (
            <span style={{ color: 'var(--color-text-muted)', marginLeft: 6 }}>
              ({t('factor.definitionOnly')})
            </span>
          )}
        </span>
      ),
    },
    {
      key: 'name',
      label: t('factor.col.name'),
      sortable: true,
      sortValue: (row) => row.name,
      render: (row) => row.name,
    },
    {
      key: 'category',
      label: t('factor.col.category'),
      sortable: true,
      sortValue: (row) => row.category,
      render: (row) => row.category,
    },
    {
      key: 'direction',
      label: t('factor.col.direction'),
      sortable: true,
      sortValue: (row) => row.direction,
      render: (row) => t(`factor.direction.${row.direction}`),
    },
    {
      key: 'last_date',
      label: t('factor.col.lastDate'),
      align: 'right',
      sortable: true,
      sortValue: (row) => row.last_date ?? '',
      render: (row) => row.last_date ?? '—',
    },
    {
      key: 'value_count',
      label: t('factor.col.values'),
      align: 'right',
      sortable: true,
      sortValue: (row) => row.value_count,
      render: (row) => row.value_count.toLocaleString(),
    },
  ];

  return (
    <div className="page-card">
      <h1 className="page-title">{t('nav.factor')}</h1>
      <p style={{ color: 'var(--color-text-muted)', marginBottom: 'var(--space-3)' }}>
        {t('factor.subtitle')}
      </p>

      <div
        style={{
          display: 'flex',
          gap: 'var(--space-3)',
          flexWrap: 'wrap',
          alignItems: 'flex-end',
          marginBottom: 'var(--space-3)',
        }}
      >
        <div className="form-row" style={{ maxWidth: 220 }}>
          <label>{t('factor.search')}</label>
          <input
            type="search"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="mom, 动量, EP"
          />
        </div>
        <div className="form-row" style={{ maxWidth: 180 }}>
          <label>{t('factor.col.category')}</label>
          <select value={category} onChange={(e) => setCategory(e.target.value)}>
            <option value="">{t('factor.allCategories')}</option>
            {categories.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
        </div>
        <label style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
          <input
            type="checkbox"
            checked={computableOnly}
            onChange={(e) => setComputableOnly(e.target.checked)}
          />
          {t('factor.computableOnly')}
        </label>
        <span style={{ color: 'var(--color-text-muted)', fontSize: 'var(--text-sm)' }}>
          {t('factor.counts', {
            total: factors.length,
            computable: factors.filter((f) => f.is_computable).length,
            shown: visible.length,
          })}
        </span>
      </div>

      <DataTable
        columns={columns}
        rows={visible}
        rowKey={(row) => row.code}
        loading={loading}
        loadingLabel={t('factor.loading')}
        empty={t('factor.empty')}
        defaultSortCol="code"
      />

      <p style={{ marginTop: 'var(--space-3)', fontSize: 'var(--text-sm)', color: 'var(--color-text-muted)' }}>
        {t('factor.pickHint')}
      </p>
    </div>
  );
}
