import { useCallback, useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { toast } from 'sonner';
import { apiFetch } from '../../utils/api';
import { DataTable, type Column } from '../DataTable';

type Factor = {
  code: string;
  name: string;
  category: string;
  direction: string;
  value_count: number;
  stock_count: number;
  last_date: string | null;
  is_computable: boolean;
};

type Condition = { code: string; top: number };

type ScreenRow = {
  ts_code: string;
  name: string | null;
  industry: string | null;
  values: Record<string, number | null>;
};

type ScreenResult = {
  trade_date: string | null;
  factors: { code: string; name: string; direction: string; trade_date: string; coverage: number }[];
  total: number;
  rows: ScreenRow[];
};

type Props = {
  portfolios: string[];
  bulkPortfolio: string;
  onBuy: (tsCode: string) => void;
};

function parseConditions(raw: string | null): Condition[] {
  if (!raw) return [];
  return raw
    .split(',')
    .map((chunk) => chunk.trim())
    .filter(Boolean)
    .map((chunk) => {
      const [code, top] = chunk.split(':');
      return { code, top: Number(top) || 20 };
    });
}

/** 因子选股：多个「前 N%」条件求交集（后端按每个因子的方向排序）。 */
export function FactorScreen({ portfolios, bulkPortfolio, onBuy }: Props) {
  const { t } = useTranslation();
  const [searchParams, setSearchParams] = useSearchParams();
  const [catalogue, setCatalogue] = useState<Factor[]>([]);
  const [conditions, setConditions] = useState<Condition[]>(() => parseConditions(searchParams.get('factors')));
  const [result, setResult] = useState<ScreenResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [selected, setSelected] = useState<Set<string>>(new Set());

  useEffect(() => {
    apiFetch<{ factors: Factor[] }>('/api/factors')
      .then((d) => setCatalogue(d.factors ?? []))
      .catch(() => setCatalogue([]));
  }, []);

  const run = useCallback(
    async (next: Condition[]) => {
      if (next.length === 0) {
        setResult(null);
        return;
      }
      setLoading(true);
      try {
        const query = next.map((c) => `${c.code}:${c.top}`).join(',');
        const data = await apiFetch<ScreenResult>(
          `/api/factors/screen?factors=${encodeURIComponent(query)}`,
        );
        setResult(data);
        setSelected(new Set());
        const params = new URLSearchParams(searchParams);
        params.set('tab', 'factor');
        params.set('factors', query);
        setSearchParams(params, { replace: true });
      } catch (err) {
        toast.error(err instanceof Error ? err.message : t('screening.factorFailed'));
        setResult(null);
      } finally {
        setLoading(false);
      }
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [t],
  );

  useEffect(() => {
    if (conditions.length > 0 && !result) run(conditions);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function addCondition() {
    const unused = catalogue.find((f) => !conditions.some((c) => c.code === f.code));
    if (!unused) return;
    const next = [...conditions, { code: unused.code, top: 20 }];
    setConditions(next);
    run(next);
  }

  function updateCondition(index: number, patch: Partial<Condition>) {
    const next = conditions.map((c, i) => (i === index ? { ...c, ...patch } : c));
    setConditions(next);
    run(next);
  }

  function removeCondition(index: number) {
    const next = conditions.filter((_, i) => i !== index);
    setConditions(next);
    run(next);
  }

  async function addSelectedToPortfolio() {
    const codes = [...selected];
    if (!bulkPortfolio || codes.length === 0) return;
    try {
      await apiFetch(`/api/portfolios/${encodeURIComponent(bulkPortfolio)}/watchlist/bulk`, {
        method: 'POST',
        body: JSON.stringify({ ts_codes: codes }),
      });
      toast.success(t('screening.addedWatchlist', { count: codes.length, portfolio: bulkPortfolio }));
    } catch (err) {
      toast.error(err instanceof Error ? err.message : t('screening.factorFailed'));
    }
  }

  const factorCodes = result?.factors.map((f) => f.code) ?? [];
  const columns: Column<ScreenRow>[] = [
    { key: 'ts_code', label: t('quote.col.ts_code'), render: (row) => row.ts_code },
    { key: 'name', label: t('quote.col.name'), render: (row) => row.name ?? '—' },
    { key: 'industry', label: t('quote.col.industry'), render: (row) => row.industry ?? '—' },
    ...factorCodes.map<Column<ScreenRow>>((code) => ({
      key: code,
      label: code,
      align: 'right',
      render: (row) => (row.values[code] == null ? '—' : String(row.values[code])),
    })),
    {
      key: 'actions',
      label: t('quote.col.actions'),
      render: (row) => (
        <button type="button" className="btn btn-sm btn-secondary" onClick={() => onBuy(row.ts_code)}>
          {t('screening.buyNow')}
        </button>
      ),
    },
  ];

  return (
    <>
      <div className="screening-factor-bar">
        {conditions.map((condition, index) => (
          <span key={`${condition.code}-${index}`} className="screening-factor-chip">
            <select
              value={condition.code}
              onChange={(e) => updateCondition(index, { code: e.target.value })}
              aria-label={t('screening.factorPick')}
            >
              {catalogue.map((factor) => (
                <option key={factor.code} value={factor.code}>
                  {factor.code} · {factor.name}
                </option>
              ))}
            </select>
            <label>
              {t('screening.factorTop')}
              <input
                type="number"
                min={1}
                max={100}
                value={condition.top}
                onChange={(e) => updateCondition(index, { top: Number(e.target.value) || 20 })}
              />
              %
            </label>
            <button type="button" className="btn btn-sm btn-secondary" onClick={() => removeCondition(index)}>
              ×
            </button>
          </span>
        ))}
        <button type="button" className="btn btn-sm" onClick={addCondition} disabled={catalogue.length === 0}>
          {t('screening.factorAdd')}
        </button>
      </div>

      {result && (
        <p className="screening-factor-meta">
          {t('screening.factorMeta', {
            count: result.total,
            date: result.trade_date ?? '—',
          })}
          {result.factors.map((factor) => (
            <span key={factor.code}>
              {' · '}
              {factor.code} {t('screening.factorCoverage', { count: factor.coverage })}
            </span>
          ))}
        </p>
      )}

      <div className="screening-factor-actions">
        <span>{t('screening.selectedCount', { count: selected.size })}</span>
        {portfolios.length > 0 && (
          <button
            type="button"
            className="btn btn-sm btn-secondary"
            onClick={addSelectedToPortfolio}
            disabled={selected.size === 0}
          >
            {t('screening.bulkWatchlist', { count: selected.size })}
          </button>
        )}
      </div>

      <DataTable
        columns={columns}
        rows={result?.rows ?? []}
        rowKey={(row) => row.ts_code}
        loading={loading}
        loadingLabel={t('screening.factorLoading')}
        empty={t('screening.factorEmpty')}
        selectable
        selected={selected}
        onToggleRow={(key) =>
          setSelected((prev) => {
            const next = new Set(prev);
            if (next.has(key)) next.delete(key);
            else next.add(key);
            return next;
          })
        }
        onToggleAll={(checked) => setSelected(checked ? new Set((result?.rows ?? []).map((r) => r.ts_code)) : new Set())}
      />
    </>
  );
}
