import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { toast } from 'sonner';
import { apiFetch } from '../../utils/api';
import './TradeDrawer.scss';

export type TradeTarget = {
  ts_code: string;
  avg_cost?: number | null;
  current_price?: number | null;
  hold_shares?: number;
};

type Props = {
  portfolio: string;
  target: TradeTarget;
  initialSide?: 'buy' | 'sell';
  onClose: () => void;
  onSaved?: () => void;
};

function todayIso(): string {
  const now = new Date();
  const local = new Date(now.getTime() - now.getTimezoneOffset() * 60_000);
  return local.toISOString().slice(0, 10);
}

/**
 * Records a buy/sell for one symbol. Bookkeeping only — it writes a `portfolio_transactions`
 * row through the API and never talks to a broker.
 */
export function TradeDrawer({ portfolio, target, initialSide = 'buy', onClose, onSaved }: Props) {
  const { t } = useTranslation();
  const available = target.hold_shares ?? 0;
  const [side, setSide] = useState<'buy' | 'sell'>(initialSide);
  const [tradeDate, setTradeDate] = useState(todayIso());
  const [shares, setShares] = useState(initialSide === 'sell' ? String(available) : '');
  const [price, setPrice] = useState(
    target.current_price != null ? String(target.current_price) : target.avg_cost != null ? String(target.avg_cost) : '',
  );
  const [fee, setFee] = useState('');
  const [note, setNote] = useState('');
  const [submitting, setSubmitting] = useState(false);

  function switchSide(next: 'buy' | 'sell') {
    if (next === 'sell' && available <= 0) return;
    setSide(next);
    setShares(next === 'sell' ? String(available) : '');
  }

  async function submit() {
    const parsedShares = Number(shares);
    const parsedPrice = Number(price);
    if (!Number.isFinite(parsedShares) || parsedShares <= 0 || Math.floor(parsedShares) !== parsedShares) {
      toast.error(t('portfolio.tradeInvalidShares'));
      return;
    }
    if (!Number.isFinite(parsedPrice) || parsedPrice <= 0) {
      toast.error(t('portfolio.tradeInvalidPrice'));
      return;
    }
    if (side === 'sell' && parsedShares > available) {
      toast.error(t('portfolio.tradeInsufficient', { available }));
      return;
    }
    setSubmitting(true);
    try {
      await apiFetch(`/api/portfolios/${encodeURIComponent(portfolio)}/transactions`, {
        method: 'POST',
        body: JSON.stringify({
          ts_code: target.ts_code,
          side,
          shares: parsedShares,
          price: parsedPrice,
          trade_date: tradeDate,
          fee: fee === '' ? 0 : Number(fee),
          reason: note,
        }),
      });
      toast.success(t('portfolio.tradeSaved'));
      onSaved?.();
      onClose();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : t('portfolio.tradeFailed'));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="trade-drawer-backdrop" role="presentation" onClick={onClose}>
      <aside
        className="trade-drawer"
        role="dialog"
        aria-modal="true"
        aria-label={side === 'buy' ? t('portfolio.tradeBuyTitle') : t('portfolio.tradeSellTitle')}
        onClick={(e) => e.stopPropagation()}
      >
        <h2 className="trade-drawer-title">
          {side === 'buy' ? t('portfolio.tradeBuyTitle') : t('portfolio.tradeSellTitle')}
        </h2>
        <p className="trade-drawer-code">{target.ts_code}</p>

        <div className="trade-drawer-sides" role="group">
          <button
            type="button"
            className={side === 'buy' ? 'btn btn-sm btn-primary' : 'btn btn-sm btn-secondary'}
            onClick={() => switchSide('buy')}
          >
            {t('portfolio.sideBuy')}
          </button>
          <button
            type="button"
            className={side === 'sell' ? 'btn btn-sm btn-primary' : 'btn btn-sm btn-secondary'}
            onClick={() => switchSide('sell')}
            disabled={available <= 0}
            title={available <= 0 ? t('portfolio.actionSellDisabled') : undefined}
          >
            {t('portfolio.sideSell')}
          </button>
        </div>
        {side === 'sell' && <p className="trade-drawer-hint">{t('portfolio.tradeAvailable', { shares: available })}</p>}

        <div className="form-row">
          <label htmlFor="trade-date">{t('portfolio.tradeDate')}</label>
          <input id="trade-date" type="date" value={tradeDate} onChange={(e) => setTradeDate(e.target.value)} />
        </div>
        <div className="form-row">
          <label htmlFor="trade-shares">{t('portfolio.colShares')}</label>
          <input
            id="trade-shares"
            type="number"
            min={1}
            step={100}
            value={shares}
            onChange={(e) => setShares(e.target.value)}
          />
        </div>
        <div className="form-row">
          <label htmlFor="trade-price">{t('portfolio.colPrice')}</label>
          <input
            id="trade-price"
            type="number"
            min={0}
            step="0.01"
            value={price}
            onChange={(e) => setPrice(e.target.value)}
          />
        </div>
        <div className="form-row">
          <label htmlFor="trade-fee">{t('portfolio.tradeFee')}</label>
          <input
            id="trade-fee"
            type="number"
            min={0}
            step="0.01"
            value={fee}
            placeholder="0"
            onChange={(e) => setFee(e.target.value)}
          />
        </div>
        <div className="form-row">
          <label htmlFor="trade-note">{t('portfolio.tradeNote')}</label>
          <input id="trade-note" type="text" value={note} onChange={(e) => setNote(e.target.value)} />
        </div>

        <div className="trade-drawer-actions">
          <button type="button" className="btn btn-primary" onClick={submit} disabled={submitting}>
            {submitting ? t('portfolio.tradeSubmitting') : t('portfolio.tradeSubmit')}
          </button>
          <button type="button" className="btn btn-secondary" onClick={onClose} disabled={submitting}>
            {t('portfolio.tradeCancel')}
          </button>
        </div>
      </aside>
    </div>
  );
}
