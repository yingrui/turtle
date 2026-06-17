import { NavLink, Outlet } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import {
  Home,
  Database,
  Filter,
  Play,
  CandlestickChart,
  LineChart,
  TrendingUp,
  ListTodo,
  Star,
  Sun,
  Moon,
} from 'lucide-react';
import { useEffect, useState } from 'react';
import { useAuth } from '../../contexts/AuthContext';
import { AppBrand } from '../AppBrand';
import { UserMenu } from './UserMenu';
import '../../App.scss';

const navItems = [
  { to: '/', icon: Home, key: 'home', end: true },
  { to: '/data', icon: Database, key: 'data', end: true },
  { to: '/watchlist', icon: Star, key: 'watchlist', end: true },
  { to: '/screening', icon: Filter, key: 'screening', end: true },
  { to: '/simulation', icon: Play, key: 'simulation', end: false },
  { to: '/market', icon: CandlestickChart, key: 'quote', end: true },
  { to: '/stocks', icon: LineChart, key: 'stocks', end: true },
  { to: '/forecast', icon: TrendingUp, key: 'forecast', end: true },
  { to: '/jobs', icon: ListTodo, key: 'jobs', end: true },
] as const;

export function MainLayout() {
  const { t } = useTranslation();
  const { user, logout } = useAuth();
  const [theme, setTheme] = useState<'light' | 'dark'>('light');

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
  }, [theme]);

  return (
    <div className="app-layout">
      <aside className="app-sidebar">
        <AppBrand />
        <nav className="app-sidebar-nav">
          {navItems.map(({ to, icon: Icon, key, end }) => (
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
        </nav>
      </aside>
      <main className="app-main">
        <header className="app-header">
          <div className="app-header-toolbar">
            <button
              type="button"
              className="app-header-icon-btn"
              onClick={() => setTheme(theme === 'light' ? 'dark' : 'light')}
              aria-label="Toggle theme"
            >
              {theme === 'light' ? <Moon size={18} /> : <Sun size={18} />}
            </button>
            <span className="app-header-divider" aria-hidden />
            <UserMenu user={user} onLogout={logout} />
          </div>
        </header>
        <div className="app-content">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
