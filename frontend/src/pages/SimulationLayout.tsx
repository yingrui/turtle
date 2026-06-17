import { NavLink, Outlet } from 'react-router-dom';
import { useTranslation } from 'react-i18next';

export function SimulationLayout() {
  const { t } = useTranslation();

  return (
    <div className="page-card">
      <h1 className="page-title">{t('nav.simulation')}</h1>
      <nav className="simulation-subnav" aria-label={t('nav.simulation')}>
        <NavLink
          to="/simulation"
          end
          className={({ isActive }) => `simulation-subnav__link${isActive ? ' simulation-subnav__link--active' : ''}`}
        >
          {t('simulation.tabRun')}
        </NavLink>
        <NavLink
          to="/simulation/results"
          className={({ isActive }) => `simulation-subnav__link${isActive ? ' simulation-subnav__link--active' : ''}`}
        >
          {t('simulation.tabResults')}
        </NavLink>
      </nav>
      <Outlet />
    </div>
  );
}
