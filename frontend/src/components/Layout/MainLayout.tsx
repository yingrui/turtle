import { NavLink, Outlet } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import {
  Home,
  Filter,
  FlaskConical,
  Play,
  CandlestickChart,
  Briefcase,
  Moon,
  Settings as SettingsIcon,
  Sun,
} from 'lucide-react';
import { useEffect, useState } from 'react';
import { useAuth } from '../../contexts/AuthContext';
import { PortfolioProvider } from '../../contexts/PortfolioContext';
import { AppBrand } from '../AppBrand';
import { DataFreshnessChip } from './DataFreshnessChip';
import { PortfolioSwitcher } from './PortfolioSwitcher';
import { HealthIndicator } from './HealthIndicator';
import { UserMenu } from './UserMenu';
import { applyTheme, readTheme, type Theme } from '../../utils/theme';
import '../../App.scss';

const navGroups = [
  {
    key: 'research',
    items: [
      { to: '/', icon: Home, key: 'home', end: true },
      { to: '/screening', icon: Filter, key: 'screening', end: true },
      { to: '/factor', icon: FlaskConical, key: 'factor', end: false },
      { to: '/market', icon: CandlestickChart, key: 'quote', end: true },
    ],
  },
  {
    key: 'portfolio',
    items: [
      { to: '/portfolio', icon: Briefcase, key: 'portfolio', end: false },
      { to: '/simulation', icon: Play, key: 'simulation', end: false },
    ],
  },
] as const;

function Sidebar() {
  const { t } = useTranslation();
  return (
    <aside className="app-sidebar">
      <AppBrand />
      <nav className="app-sidebar-nav">
        {navGroups.map((group) => (
          <div key={group.key} className="app-sidebar-group">
            <span className="app-sidebar-group-label">{t(`navGroup.${group.key}`)}</span>
            {group.items.map(({ to, icon: Icon, key, end }) => (
              <NavLink
                key={to}
                to={to}
                end={end}
                className={({ isActive }) => `app-sidebar-link${isActive ? ' active' : ''}`}
              >
                <Icon size={18} />
                <span>{t(`nav.${key}`)}</span>
              </NavLink>
            ))}
          </div>
        ))}
      </nav>
      <div className="app-sidebar-footer">
        <NavLink
          to="/settings"
          className={({ isActive }) => `app-sidebar-link${isActive ? ' active' : ''}`}
        >
          <SettingsIcon size={18} />
          <span>{t('nav.settings')}</span>
        </NavLink>
      </div>
    </aside>
  );
}

function Header() {
  const { t } = useTranslation();
  const { user, logout, authMode } = useAuth();
  const [theme, setTheme] = useState<Theme>(readTheme);

  useEffect(() => {
    applyTheme(theme);
  }, [theme]);

  return (
    <header className="app-header">
      <div className="app-header-context">
        <DataFreshnessChip />
        <PortfolioSwitcher />
      </div>
      <div className="app-header-toolbar">
        <HealthIndicator />
        <span className="app-header-divider" aria-hidden />
        <button
          type="button"
          className="app-header-icon-btn"
          onClick={() => setTheme(theme === 'light' ? 'dark' : 'light')}
          aria-label={t('header.toggleTheme')}
          title={t('header.toggleTheme')}
        >
          {theme === 'light' ? <Moon size={18} /> : <Sun size={18} />}
        </button>
        <span className="app-header-divider" aria-hidden />
        <UserMenu user={user} onLogout={logout} showLogout={authMode === 'local'} />
      </div>
    </header>
  );
}

export function MainLayout() {
  useEffect(() => {
    applyTheme(readTheme());
  }, []);

  return (
    <PortfolioProvider>
      <div className="app-layout">
        <Sidebar />
        <main className="app-main">
          <Header />
          <div className="app-content">
            <Outlet />
          </div>
        </main>
      </div>
    </PortfolioProvider>
  );
}
