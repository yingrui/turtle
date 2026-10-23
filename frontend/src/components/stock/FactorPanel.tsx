import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { apiFetch } from '../../utils/api';
import { DataTable, type Column } from '../DataTable';

type FactorValue = {
  code: string;
  name: string;
  category: string;
  direction: string;
  unit: string | null;
  trade_date: string;
  value: number | null;
};

/** Latest factor values for one symbol — the 因子 tab on the stock page. */
export function FactorPanel({ tsCode }: { tsCode: string }) {
  const { t } = useTranslation();
  const [rows, setRows] = useState<FactorValue[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    apiFetch<{ factors: FactorValue[] }>(`/api/stocks/${encodeURIComponent(tsCode)}/factors`)
      .then((d) => setRows(d.factors ?? []))
      .catch(() => setRows([]))
      .finally(() => setLoading(false));
  }, [tsCode]);

  const columns: Column<FactorValue>[] = [
    { key: 'code', label: t('factor.col.code'), render: (row) => row.code },
    { key: 'name', label: t('factor.col.name'), render: (row) => row.name },
    { key: 'category', label: t('factor.col.category'), render: (row) => row.category },
    { key: 'direction', label: t('factor.col.direction'), render: (row) => row.direction },
    {
      key: 'value',
      label: t('stockDetail.factor.value'),
      align: 'right',
      render: (row) => (row.value == null ? '—' : String(row.value)),
    },
    { key: 'trade_date', label: t('factor.col.date'), render: (row) => row.trade_date },
  ];

  return (
    <DataTable
      columns={columns}
      rows={rows}
      rowKey={(row) => row.code}
      loading={loading}
      loadingLabel={t('stockDetail.factor.loading')}
      empty={t('stockDetail.factor.empty')}
    />
  );
}
