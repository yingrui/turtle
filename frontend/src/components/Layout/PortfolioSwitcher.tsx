import { useTranslation } from 'react-i18next';
import { Briefcase } from 'lucide-react';
import { usePortfolioContext } from '../../contexts/PortfolioContext';

/** The single portfolio selector for the app (also persisted in localStorage). */
export function PortfolioSwitcher() {
  const { t } = useTranslation();
  const { portfolios, portfolio, setPortfolio } = usePortfolioContext();

  if (portfolios.length === 0) return null;

  return (
    <label className="header-portfolio" title={t('header.portfolioTitle')}>
      <Briefcase size={14} />
      <select
        value={portfolio}
        onChange={(e) => setPortfolio(e.target.value)}
        aria-label={t('header.portfolioTitle')}
      >
        {portfolios.map((name) => (
          <option key={name} value={name}>
            {name}
          </option>
        ))}
      </select>
    </label>
  );
}
