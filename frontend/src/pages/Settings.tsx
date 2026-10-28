import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { toast } from 'sonner';
import { apiFetch } from '../utils/api';
import { applyTheme, readTheme, type Theme } from '../utils/theme';
import './Settings.scss';

type DataStatus = {
  as_of_date: string | null;
  tables?: { name: string; latest_trade_date: string | null; rows?: number | null }[];
};

type Health = { status?: string; version?: string; [key: string]: unknown };

type DbApp = { application_name: string; state: string; count: number; oldest_idle_seconds: number | null };

type DbConnections = {
  max_connections: number;
  superuser_reserved: number;
  in_use: number;
  by_app: DbApp[];
  this_app: { connections: number; idle: number; releasable: number };
  min_idle_seconds: number;
};

export function Settings() {
  const { t, i18n } = useTranslation();
  const [theme, setTheme] = useState<Theme>(readTheme);
  const [language, setLanguage] = useState(i18n.resolvedLanguage ?? 'zh-CN');
  const [data, setData] = useState<DataStatus | null>(null);
  const [health, setHealth] = useState<Health | null>(null);
  const [dbInfo, setDbInfo] = useState<DbConnections | null>(null);
  const [releasing, setReleasing] = useState(false);

  useEffect(() => {
    apiFetch<DataStatus>('/api/data/status').then(setData).catch(() => setData(null));
    apiFetch<Health>('/api/health').then(setHealth).catch(() => setHealth(null));
    loadDb().catch(() => setDbInfo(null));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function loadDb() {
    setDbInfo(await apiFetch<DbConnections>('/api/admin/db-connections'));
  }

  async function releaseIdleConnections() {
    setReleasing(true);
    try {
      const result = await apiFetch<{ terminated: number; after: DbConnections }>(
        '/api/admin/db-connections/release',
        { method: 'POST' },
      );
      setDbInfo(result.after);
      toast.success(t('settings.dbReleased', { count: result.terminated }));
    } catch (err) {
      toast.error(err instanceof Error ? err.message : t('settings.dbReleaseFailed'));
    } finally {
      setReleasing(false);
    }
  }

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

      </section>

      <section className="settings-section">
        <h2 className="settings-section-title">{t('settings.dbTitle')}</h2>
        <p className="settings-section-desc">{t('settings.dbDesc')}</p>
        {dbInfo ? (
          <>
            <div className="settings-readonly">
              <div>
                <span>{t('settings.dbInUse')}</span>
                <strong>
                  {dbInfo.in_use} / {dbInfo.max_connections}
                </strong>
              </div>
              <div>
                <span>{t('settings.dbThisApp')}</span>
                <strong>
                  {dbInfo.this_app.connections} ({dbInfo.this_app.idle} idle)
                </strong>
              </div>
              <div>
                <span>{t('settings.dbReleasable')}</span>
                <strong>{dbInfo.this_app.releasable}</strong>
              </div>
            </div>
            <button
              type="button"
              className="btn btn-secondary"
              disabled={releasing || dbInfo.this_app.releasable === 0}
              onClick={releaseIdleConnections}
            >
              {releasing ? t('settings.dbReleasing') : t('settings.dbRelease')}
            </button>
            <p className="settings-section-desc" style={{ marginTop: 'var(--space-2)' }}>
              {t('settings.dbHint', { seconds: dbInfo.min_idle_seconds })}
            </p>
          </>
        ) : (
          <p className="settings-section-desc">{t('settings.dbUnavailable')}</p>
        )}
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
