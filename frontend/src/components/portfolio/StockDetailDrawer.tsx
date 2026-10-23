import { useState } from 'react';
import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import './StockDetailDrawer.scss';

export type HoldingRow = {
  ts_code: string;
  status: string;
  hold_shares: number;
  avg_cost: number;
  total_cost: number;
  current_price?: number;
  market_value?: number;
  unrealized_pnl?: number;
  unrealized_pct?: number | null;
  realized_pnl: number;
  holding_days: number | null;
  first_buy_date: string | null;
  last_trade_date: string | null;
  stop_loss_point: number | null;
  max_holding_days: number | null;
  target_amount: number | null;
  note?: string;
};

type Props = {
  stock: HoldingRow;
  flags: { level: 'warn' | 'danger'; label: string }[];
  money: (value: number | null | undefined) => string;
  onClose: () => void;
  onPatch: (patch: Record<string, number | null>) => void;
  onTrade: (side: 'buy' | 'sell') => void;
};

const EDITABLE = [
  { key: 'stop_loss_point', label: 'colStopLoss', step: '0.01' },
  { key: 'target_amount', label: 'colTarget', step: '1' },
  { key: 'max_holding_days', label: 'colMaxHolding', step: '1' },
] as const;

/** Read-mostly detail panel for one holding: the columns the table no longer shows. */
export function StockDetailDrawer({ stock, flags, money, onClose, onPatch, onTrade }: Props) {
  const { t } = useTranslation();
  const [draft, setDraft] = useState<Record<string, string>>({
    stop_loss_point: stock.stop_loss_point != null ? String(stock.stop_loss_point) : '',
    target_amount: stock.target_amount != null ? String(stock.target_amount) : '',
    max_holding_days: stock.max_holding_days != null ? String(stock.max_holding_days) : '',
  });

  function commit(key: string) {
    const raw = draft[key]?.trim() ?? '';
    const next = raw === '' ? null : Number(raw);
    const current = (stock[key as keyof HoldingRow] as number | null) ?? null;
    if (next !== current) onPatch({ [key]: next });
  }

  const facts: { label: string; value: string; tone?: string }[] = [
    { label: t('portfolio.colShares'), value: String(stock.hold_shares) },
    { label: t('portfolio.colAvgCost'), value: money(stock.avg_cost) },
    { label: t('portfolio.colTotalCost'), value: money(stock.total_cost) },
    { label: t('portfolio.colLastPrice'), value: money(stock.current_price) },
    { label: t('portfolio.colMarketValue'), value: money(stock.market_value) },
    {
      label: t('portfolio.colUnrealized'),
      value:
        stock.unrealized_pnl == null
          ? '—'
          : `${money(stock.unrealized_pnl)}${stock.unrealized_pct != null ? ` (${stock.unrealized_pct}%)` : ''}`,
      tone: (stock.unrealized_pnl ?? 0) < 0 ? 'price-down' : 'price-up',
    },
    {
      label: t('portfolio.colRealized'),
      value: money(stock.realized_pnl),
      tone: stock.realized_pnl < 0 ? 'price-down' : 'price-up',
    },
    { label: t('portfolio.colHolding'), value: stock.holding_days == null ? '—' : String(stock.holding_days) },
    { label: t('portfolio.colFirstBuy'), value: stock.first_buy_date ?? '—' },
    { label: t('portfolio.colLastTrade'), value: stock.last_trade_date ?? '—' },
  ];

  return (
    <div className="detail-drawer-backdrop" role="presentation" onClick={onClose}>
      <aside
        className="detail-drawer"
        role="dialog"
        aria-modal="true"
        aria-label={stock.ts_code}
        onClick={(e) => e.stopPropagation()}
      >
        <header className="detail-drawer-head">
          <div>
            <h2 className="detail-drawer-title">{stock.ts_code}</h2>
            <Link to={`/stocks/${encodeURIComponent(stock.ts_code)}`}>{t('portfolio.openStock')}</Link>
          </div>
          <button type="button" className="btn btn-sm btn-secondary" onClick={onClose}>
            {t('portfolio.close')}
          </button>
        </header>

        {flags.length > 0 && (
          <p className="detail-drawer-flags">
            {flags.map((flag) => (
              <span key={flag.label} className={`portfolio-flag portfolio-flag--${flag.level}`}>
                {flag.label}
              </span>
            ))}
          </p>
        )}

        <dl className="detail-drawer-facts">
          {facts.map((fact) => (
            <div key={fact.label}>
              <dt>{fact.label}</dt>
              <dd className={fact.tone}>{fact.value}</dd>
            </div>
          ))}
        </dl>

        <h3 className="detail-drawer-subtitle">{t('portfolio.editableTitle')}</h3>
        <div className="detail-drawer-edit">
          {EDITABLE.map((field) => (
            <label key={field.key}>
              <span>{t(`portfolio.${field.label}`)}</span>
              <input
                type="number"
                step={field.step}
                value={draft[field.key]}
                onChange={(e) => setDraft({ ...draft, [field.key]: e.target.value })}
                onBlur={() => commit(field.key)}
              />
            </label>
          ))}
        </div>

        {stock.note ? <p className="detail-drawer-note">{stock.note}</p> : null}

        <div className="detail-drawer-actions">
          <button type="button" className="btn btn-primary" onClick={() => onTrade('buy')}>
            {t('portfolio.actionBuy')}
          </button>
          <button
            type="button"
            className="btn btn-secondary"
            onClick={() => onTrade('sell')}
            disabled={stock.hold_shares <= 0}
          >
            {t('portfolio.actionSell')}
          </button>
        </div>
      </aside>
    </div>
  );
}
