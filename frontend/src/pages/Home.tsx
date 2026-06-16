import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';

const features = [
  { to: '/data', title: 'Data Collection', desc: 'Sync OHLCV, adj factors, dividends, and trade calendar from Tushare.' },
  { to: '/portfolio', title: 'Portfolio', desc: 'Create portfolios, edit watchlist, risk control, and policy parameters.' },
  { to: '/market', title: 'Market Quotes', desc: 'Browse all A-share listings with latest close, change%, and filters.' },
  { to: '/screening', title: 'Universe Screening', desc: 'Trend + ADF screening to discover candidate stocks.' },
  { to: '/simulation', title: 'Simulation', desc: 'Backtest policies: MA, Donchian, Bollinger, ensemble, ATR.' },
  { to: '/simulation/results', title: 'Results', desc: 'CAGR, equity curves, trades, per-stock P&L, multi-policy compare.' },
  { to: '/stocks', title: 'Stock Analysis', desc: 'Technical charts aligned with trading policies.' },
  { to: '/forecast', title: 'Forecast', desc: 'ARIMA price forecast with configurable horizon.' },
  { to: '/jobs', title: 'Jobs', desc: 'Background job history for data sync and simulations.' },
];

export function Home() {
  const { t } = useTranslation();

  return (
    <div className="page-card">
      <h1 className="page-title">{t('appName')}</h1>
      <p style={{ color: 'var(--color-text-muted)', lineHeight: 1.6, marginBottom: 'var(--space-6)' }}>
        Personal stock trading system for Chinese A-share markets — data pipeline, portfolio management,
        universe screening, multi-policy backtesting, and single-stock analysis.
      </p>
      <div style={{ display: 'grid', gap: 'var(--space-3)' }}>
        {features.map((f) => (
          <Link
            key={f.to}
            to={f.to}
            style={{
              display: 'block',
              padding: 'var(--space-4)',
              border: '1px solid var(--color-border)',
              borderRadius: 'var(--radius-md)',
              textDecoration: 'none',
              color: 'inherit',
            }}
          >
            <strong style={{ color: 'var(--color-accent)' }}>{f.title}</strong>
            <p style={{ margin: 'var(--space-1) 0 0', fontSize: 'var(--text-sm)', color: 'var(--color-text-muted)' }}>
              {f.desc}
            </p>
          </Link>
        ))}
      </div>
    </div>
  );
}
