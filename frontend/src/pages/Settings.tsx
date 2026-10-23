import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { toast } from 'sonner';
import { apiFetch } from '../utils/api';
import { usePortfolioContext } from '../contexts/PortfolioContext';
import { applyTheme, readTheme, type Theme } from '../utils/theme';
import './Settings.scss';

type DataStatus = {
  as_of_date: string | null;
  tables?: { name: string; latest_trade_date: string | null; rows?: number | null }[];
};

type Health = { status?: string; version?: string; [key: string]: unknown };

export function Settings() {
  const { t, i18n } = useTranslation();
  const { portfolios, portfolio, setPortfolio } = usePortfolioContext();
  const [theme, setTheme] = useState<Theme>(readTheme);
  const [language, setLanguage] = useState(i18n.resolvedLanguage ?? 'zh-CN');
  const [data, setData] = useState<DataStatus | null>(null);
  const [health, setHealth] = useState<Health | null>(null);

  useEffect(() => {
    apiFetch<DataStatus>('/api/data/status').then(setData).catch(() => setData(null));
    apiFetch<Health>('/api/health').then(setHealth).catch(() => setHealth(null));
  }, []);

  function changeTheme(next: Theme) {
    setTheme(next);
    applyTheme(next);
    toast.success(t('settings.saved'));
  }

  async function changeLanguage(next: string) {
    setLanguage(next);
    await i18n.changeLanguage(next);
    toast.success(t('settings.saved'));
  }

  return (
    <div className="page-card settings-page">
      <h1 className="page-title">{t('nav.settings')}</h1>
      <p className="page-subtitle">{t('settings.subtitle')}</p>

      <section className="settings-section">
        <h2 className="settings-section-title">{t('settings.preferencesTitle')}</h2>
        <p className="settings-section-desc">{t('settings.preferencesDesc')}</p>

        <div className="settings-field">
          <label htmlFor="settings-language">{t('settings.language')}</label>
          <select
            id="settings-language"
            value={language}
            onChange={(e) => changeLanguage(e.target.value)}
          >
            <option value="zh-CN">简体中文</option>
            <option value="en">English</option>
          </select>
        </div>

        <div className="settings-field">
          <label htmlFor="settings-theme">{t('settings.theme')}</label>
          <select id="settings-theme" value={theme} onChange={(e) => changeTheme(e.target.value as Theme)}>
            <option value="light">{t('settings.themeLight')}</option>
            <option value="dark">{t('settings.themeDark')}</option>
          </select>
        </div>

        <div className="settings-field">
          <label htmlFor="settings-portfolio">{t('settings.defaultPortfolio')}</label>
          <select
            id="settings-portfolio"
            value={portfolio}
            onChange={(e) => setPortfolio(e.target.value)}
            disabled={portfolios.length === 0}
          >
            {portfolios.length === 0 && <option value="">—</option>}
            {portfolios.map((name) => (
              <option key={name} value={name}>
                {name}
              </option>
            ))}
          </select>
        </div>
      </section>

      <section className="settings-section">
        <h2 className="settings-section-title">{t('settings.dataTitle')}</h2>
        <p className="settings-section-desc">{t('settings.dataDesc')}</p>
        <div className="settings-readonly">
          <div>
            <span>{t('settings.asOf')}</span>
            <strong>{data?.as_of_date ?? t('settings.unknown')}</strong>
          </div>
          {(data?.tables ?? []).map((table) => (
            <div key={table.name}>
              <span>{table.name}</span>
              <strong>{table.latest_trade_date ?? t('settings.unknown')}</strong>
            </div>
          ))}
        </div>
        <p className="settings-hint">{t('settings.dataHint')}</p>
      </section>

      <section className="settings-section">
        <h2 className="settings-section-title">{t('settings.diagnosticsTitle')}</h2>
        <p className="settings-section-desc">{t('settings.diagnosticsDesc')}</p>
        <div className="settings-readonly">
          <div>
            <span>{t('settings.health')}</span>
            <strong>{String(health?.status ?? t('settings.unknown'))}</strong>
          </div>
          <div>
            <span>{t('settings.version')}</span>
            <strong>{String(health?.version ?? t('settings.unknown'))}</strong>
          </div>
        </div>
      </section>
    </div>
  );
}
