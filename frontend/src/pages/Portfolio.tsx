import { useCallback, useEffect, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { toast } from 'sonner';
import { apiFetch } from '../utils/api';
import './Portfolio.scss';

type PortfolioConfig = {
  name?: string;
  follow_stocks?: string[];
  policies?: unknown[];
  risk_control?: Record<string, unknown>;
  initial_investment?: number;
};

export function Portfolio() {
  const { t } = useTranslation();
  const [searchParams] = useSearchParams();
  const [portfolios, setPortfolios] = useState<string[]>([]);
  const [name, setName] = useState(searchParams.get('portfolio') ?? '');
  const [yaml, setYaml] = useState('');
  const [summary, setSummary] = useState<PortfolioConfig | null>(null);
  const [saving, setSaving] = useState(false);
  const [loadingList, setLoadingList] = useState(true);

  const loadList = useCallback(async () => {
    const d = await apiFetch<{ portfolios: string[] }>('/api/portfolios');
    setPortfolios(d.portfolios);
    const fromUrl = searchParams.get('portfolio');
    const next =
      fromUrl && d.portfolios.includes(fromUrl)
        ? fromUrl
        : d.portfolios.includes(name)
          ? name
          : d.portfolios[0] ?? '';
    setName(next);
  }, [name, searchParams]);

  useEffect(() => {
    loadList()
      .catch(() => toast.error(t('portfolio.loadError')))
      .finally(() => setLoadingList(false));
  }, [loadList, t]);

  useEffect(() => {
    if (!name) {
      setYaml('');
      setSummary(null);
      return;
    }
    apiFetch<{ yaml: string }>(`/api/portfolios/${encodeURIComponent(name)}/yaml`)
      .then((d) => setYaml(d.yaml))
      .catch(() => toast.error(t('portfolio.loadError')));
    apiFetch<PortfolioConfig>(`/api/portfolios/${encodeURIComponent(name)}`)
      .then(setSummary)
      .catch(() => setSummary(null));
  }, [name, t]);

  async function onSave() {
    setSaving(true);
    try {
      await apiFetch(`/api/portfolios/${encodeURIComponent(name)}/yaml`, {
        method: 'PUT',
        body: JSON.stringify({ yaml }),
      });
      toast.success(t('portfolio.saved'));
      const cfg = await apiFetch<PortfolioConfig>(`/api/portfolios/${encodeURIComponent(name)}`);
      setSummary(cfg);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : t('portfolio.saveFailed'));
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="page-card portfolio-page">
      <p className="portfolio-breadcrumb">
        <Link to={name ? `/watchlist?portfolio=${encodeURIComponent(name)}` : '/watchlist'}>
          ← {t('nav.watchlist')}
        </Link>
      </p>
      <h1 className="page-title">{t('portfolio.configPageTitle')}</h1>
      <p className="portfolio-intro">{t('portfolio.configPageDesc')}</p>

      {loadingList ? (
        <p className="portfolio-muted">{t('portfolio.loading')}</p>
      ) : portfolios.length === 0 ? (
        <div className="portfolio-empty">
          <p className="portfolio-muted">{t('portfolio.noPortfolioForConfig')}</p>
          <Link to="/watchlist" className="btn btn-primary">
            {t('watchlist.createPortfolio')}
          </Link>
        </div>
      ) : (
        <>
          <div className="form-row" style={{ maxWidth: 280, marginBottom: 'var(--space-4)' }}>
            <label htmlFor="portfolio-config-select">{t('portfolio.select')}</label>
            <select id="portfolio-config-select" value={name} onChange={(e) => setName(e.target.value)}>
              {portfolios.map((p) => (
                <option key={p} value={p}>{p}</option>
              ))}
            </select>
          </div>

          {name && summary && (
            <section className="portfolio-editor">
              <div className="stat-grid">
                <div className="stat-card">
                  <span>{t('portfolio.statStocks')}</span>
                  <strong>{summary.follow_stocks?.length ?? 0}</strong>
                </div>
                <div className="stat-card">
                  <span>{t('portfolio.statPolicies')}</span>
                  <strong>{summary.policies?.length ?? 0}</strong>
                </div>
                <div className="stat-card">
                  <span>{t('portfolio.statCapital')}</span>
                  <strong>{summary.initial_investment?.toLocaleString() ?? '—'}</strong>
                </div>
              </div>

              <h2 className="portfolio-panel-title">{t('portfolio.configTitle')}</h2>
              <p className="portfolio-panel-desc">{t('portfolio.configDesc')}</p>
              <textarea
                className="yaml-editor"
                value={yaml}
                onChange={(e) => setYaml(e.target.value)}
                spellCheck={false}
                aria-label={t('portfolio.configTitle')}
              />
              <div className="portfolio-save-row">
                <button
                  type="button"
                  className="btn btn-primary"
                  onClick={onSave}
                  disabled={saving || !yaml}
                >
                  {saving ? t('portfolio.saving') : t('portfolio.save')}
                </button>
              </div>
            </section>
          )}
        </>
      )}
    </div>
  );
}
