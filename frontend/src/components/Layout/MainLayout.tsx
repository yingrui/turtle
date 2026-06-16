import { NavLink, Outlet } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import {
  Home,
  Database,
  FolderOpen,
  Filter,
  Play,
  BarChart3,
  CandlestickChart,
  LineChart,
  TrendingUp,
  ListTodo,
  Sun,
  Moon,
  LogOut,
} from 'lucide-react';
import { useEffect, useState } from 'react';
import { useAuth } from '../../contexts/AuthContext';
import { AppBrand } from '../AppBrand';
import '../../App.scss';

const navItems = [
  { to: '/', icon: Home, key: 'home' },
  { to: '/data', icon: Database, key: 'data' },
  { to: '/portfolio', icon: FolderOpen, key: 'portfolio' },
  { to: '/screening', icon: Filter, key: 'screening' },
  { to: '/simulation', icon: Play, key: 'simulation' },
  { to: '/simulation/results', icon: BarChart3, key: 'results' },
  { to: '/market', icon: CandlestickChart, key: 'quote' },
  { to: '/stocks', icon: LineChart, key: 'stocks' },
  { to: '/forecast', icon: TrendingUp, key: 'forecast' },
  { to: '/jobs', icon: ListTodo, key: 'jobs' },
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
          {navItems.map(({ to, icon: Icon, key }) => (
            <NavLink
              key={to}
              to={to}
              end={to === '/'}
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
          <span style={{ color: 'var(--color-text-muted)', fontSize: 'var(--text-sm)' }}>
            {user?.login}
            {user?.is_admin ? ' · admin' : ''}
          </span>
          <div style={{ display: 'flex', gap: 'var(--space-2)' }}>
            <button
              type="button"
              className="btn btn-secondary btn-sm"
              onClick={() => setTheme(theme === 'light' ? 'dark' : 'light')}
              aria-label="Toggle theme"
            >
              {theme === 'light' ? <Moon size={16} /> : <Sun size={16} />}
            </button>
            <button type="button" className="btn btn-secondary btn-sm" onClick={logout}>
              <LogOut size={16} />
              <span>{t('auth.logout')}</span>
            </button>
          </div>
        </header>
        <div className="app-content">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
