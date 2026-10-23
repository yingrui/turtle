import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { apiFetch } from '../../utils/api';
import { usePortfolioContext } from '../../contexts/PortfolioContext';
import { TradeDrawer } from '../portfolio/TradeDrawer';
import { riskFlags } from '../../utils/riskFlags';

type Stock = {
  ts_code: string;
  status: string;
  hold_shares: number;
  avg_cost: number;
  current_price?: number;
  market_value?: number;
  unrealized_pnl?: number;
  holding_days?: number | null;
  first_buy_date?: string | null;
  stop_loss_point?: number | null;
  max_holding_days?: number | null;
};

type RiskControl = Record<string, number | boolean>;

type Row = { stock: Stock; flags: { level: 'warn' | 'danger'; label: string }[] };

/** Workbench "what needs doing today": holdings that tripped a risk rule, with a sell shortcut. */
export function TodayTodo() {
  const { t } = useTranslation();
  const { portfolio } = usePortfolioContext();
  const [rows, setRows] = useState<Row[]>([]);
  const [sell, setSell] = useState<Stock | null>(null);

  function load() {
    if (!portfolio) {
      setRows([]);
      return;
    }
    Promise.all([
      apiFetch<{ stocks: Stock[] }>(`/api/portfolios/${encodeURIComponent(portfolio)}/stocks`),
      apiFetch<RiskControl>(`/api/portfolios/${encodeURIComponent(portfolio)}/risk-control`),
    ])
      .then(([stockRes, risk]) => {
        const holdings = stockRes.stocks.filter((s) => s.status === 'holding' && s.hold_shares > 0);
        const total = holdings.reduce((sum, s) => sum + (s.market_value ?? 0), 0);
        const params = {
          maxHoldingDays: risk['max_holding_period.days'] as number | undefined,
          checkHoldingPeriod: risk['max_holding_period.should_check'] !== false,
          maxPositionRatio: risk['max_position_ratio'] as number | undefined,
        };
        const labels = {
          brokenStop: t('portfolio.riskBrokenStop'),
          nearStop: t('portfolio.riskNearStop'),
          overHolding: t('portfolio.riskOverHolding'),
          holdingDue: t('portfolio.riskHoldingDue'),
          overWeight: t('portfolio.riskOverWeight'),
        };
        setRows(
          holdings
            .map((stock) => ({ stock, flags: riskFlags(stock, params, total, labels) }))
            .filter((row) => row.flags.length > 0),
        );
      })
      .catch(() => setRows([]));
  }

  useEffect(load, [portfolio, t]);

  return (
    <section className="home-panel home-todo">
      <div className="home-panel-head">
        <h2>{t('home.todoTitle')}</h2>
        <Link to={`/portfolio?tab=holdings&status=holding${portfolio ? `&portfolio=${encodeURIComponent(portfolio)}` : ''}`}>
          {t('home.viewAll')}
        </Link>
      </div>
      {rows.length === 0 ? (
        <p className="home-muted">{t('home.todoEmpty')}</p>
      ) : (
        <ul className="home-todo-list">
          {rows.map(({ stock, flags }) => (
            <li key={stock.ts_code}>
              <div className="home-todo-main">
                <Link to={`/stocks/${encodeURIComponent(stock.ts_code)}`}>{stock.ts_code}</Link>
                <span className="home-todo-flags">
                  {flags.map((flag) => (
                    <span key={flag.label} className={`portfolio-flag portfolio-flag--${flag.level}`}>
                      {flag.label}
                    </span>
                  ))}
                </span>
              </div>
              <div className="home-todo-meta">
                <span>{t('home.todoHeld', { days: stock.holding_days ?? 0 })}</span>
                <span className={((stock.unrealized_pnl ?? 0) < 0 ? 'price-down' : 'price-up')}>
                  {(stock.unrealized_pnl ?? 0).toLocaleString(undefined, { maximumFractionDigits: 0 })}
                </span>
                <button type="button" className="btn btn-sm btn-secondary" onClick={() => setSell(stock)}>
                  {t('portfolio.actionSell')}
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}

      {sell && portfolio && (
        <TradeDrawer
          portfolio={portfolio}
          target={{
            ts_code: sell.ts_code,
            avg_cost: sell.avg_cost,
            current_price: sell.current_price,
            hold_shares: sell.hold_shares,
          }}
          initialSide="sell"
          onClose={() => setSell(null)}
          onSaved={load}
        />
      )}
    </section>
  );
}
