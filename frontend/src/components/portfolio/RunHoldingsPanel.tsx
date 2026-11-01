import { useTranslation } from 'react-i18next';
import { DataTable, type Column } from '../DataTable';
import './RunHoldingsPanel.scss';

export type RunHolding = {
  ts_code: string;
  shares: number;
  price: number;
  avg_cost: number | null;
  unrealized_pnl: number | null;
  unrealized_pct: number | null;
  weight: number | null;
  opened_at: string | null;
  holding_days: number | null;
};

/** What the selected backtest held on the selected day. The run and the date are chosen above, with
 *  the portfolio, because a portfolio's holdings only mean something together with them. */
export function RunHoldingsPanel({ rows, day }: { rows: RunHolding[]; day: string }) {
  const { t } = useTranslation();

  function money(value: number | null | undefined) {
    return value == null ? '—' : value.toLocaleString(undefined, { maximumFractionDigits: 2 });
  }

  const columns: Column<RunHolding>[] = [
    { key: 'code', label: t('portfolio.colCode'), render: (row) => row.ts_code },
    { key: 'shares', label: t('portfolio.colShares'), align: 'right', render: (row) => row.shares },
    { key: 'cost', label: t('portfolio.colAvgCost'), align: 'right', render: (row) => money(row.avg_cost) },
    { key: 'price', label: t('portfolio.colLastPrice'), align: 'right', render: (row) => money(row.price) },
    {
      key: 'pnl',
      label: t('portfolio.colUnrealized'),
      align: 'right',
      render: (row) => (
        <span className={(row.unrealized_pnl ?? 0) >= 0 ? 'price-up' : 'price-down'}>
          {money(row.unrealized_pnl)}
          {row.unrealized_pct == null ? '' : `（${row.unrealized_pct.toFixed(2)}%）`}
        </span>
      ),
    },
    {
      key: 'weight',
      label: t('portfolio.colWeight'),
      align: 'right',
      render: (row) => (row.weight == null ? '—' : `${(row.weight * 100).toFixed(2)}%`),
    },
    { key: 'opened', label: t('portfolio.colOpened'), render: (row) => row.opened_at ?? '—' },
    {
      key: 'days',
      label: t('portfolio.colHoldingDays'),
      align: 'right',
      render: (row) => row.holding_days ?? '—',
    },
  ];

  return (
    <div className="run-holdings">
      <h2 className="portfolio-panel-title">{t('portfolio.runHoldingsTitle', { day: day || '—' })}</h2>
      <p className="portfolio-panel-desc">{t('portfolio.runHoldingsDesc')}</p>
      <DataTable<RunHolding>
        columns={columns}
        rows={rows}
        rowKey={(row) => row.ts_code}
        empty={t('portfolio.emptyHoldings')}
        pageSize={25}
      />
    </div>
  );
}
