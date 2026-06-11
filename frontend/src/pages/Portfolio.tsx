import { useCallback, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { toast } from 'sonner';
import { apiFetch } from '../utils/api';

type PortfolioConfig = {
  name?: string;
  follow_stocks?: string[];
  policies?: unknown[];
  risk_control?: Record<string, unknown>;
  initial_investment?: number;
};

export function Portfolio() {
  const { t } = useTranslation();
  const [portfolios, setPortfolios] = useState<string[]>([]);
  const [name, setName] = useState('');
  const [newName, setNewName] = useState('');
  const [yaml, setYaml] = useState('');
  const [summary, setSummary] = useState<PortfolioConfig | null>(null);
  const [saving, setSaving] = useState(false);
  const [creating, setCreating] = useState(false);

  const loadList = useCallback(() => {
    return apiFetch<{ portfolios: string[] }>('/api/portfolios').then((d) => {
      setPortfolios(d.portfolios);
      if (d.portfolios.length && !d.portfolios.includes(name)) {
        setName(d.portfolios[0]);
      }
    });
  }, [name]);

  useEffect(() => {
    loadList().catch(() => toast.error('Failed to load portfolios'));
  }, [loadList]);

  useEffect(() => {
    if (!name) {
      setYaml('');
      setSummary(null);
      return;
    }
    apiFetch<{ yaml: string }>(`/api/portfolios/${name}/yaml`)
      .then((d) => setYaml(d.yaml))
      .catch(() => toast.error('Failed to load portfolio'));
    apiFetch<PortfolioConfig>(`/api/portfolios/${name}`)
      .then(setSummary)
      .catch(() => setSummary(null));
  }, [name]);

  async function onCreate() {
    const trimmed = newName.trim();
    if (!trimmed) {
      toast.error('Enter a portfolio name');
      return;
    }
    setCreating(true);
    try {
      await apiFetch('/api/portfolios', {
        method: 'POST',
        body: JSON.stringify({ name: trimmed }),
      });
      toast.success('Portfolio created');
      setNewName('');
      await loadList();
      setName(trimmed);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Create failed');
    } finally {
      setCreating(false);
    }
  }

  async function onSave() {
    setSaving(true);
    try {
      await apiFetch(`/api/portfolios/${name}/yaml`, {
        method: 'PUT',
        body: JSON.stringify({ yaml }),
      });
      toast.success('Portfolio saved');
      const cfg = await apiFetch<PortfolioConfig>(`/api/portfolios/${name}`);
      setSummary(cfg);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Save failed');
    } finally {
      setSaving(false);
    }
  }

  async function onDelete() {
    if (!name || !window.confirm(`Delete portfolio "${name}"?`)) return;
    try {
      await apiFetch(`/api/portfolios/${name}`, { method: 'DELETE' });
      toast.success('Portfolio deleted');
      setName('');
      setYaml('');
      setSummary(null);
      await loadList();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Delete failed');
    }
  }

  return (
    <div className="page-card">
      <h1 className="page-title">{t('nav.portfolio')}</h1>
      <p style={{ color: 'var(--color-text-muted)', marginBottom: 'var(--space-4)' }}>
        Create and edit portfolios stored in the database — watchlist, risk control, and trading policies.
      </p>

      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 'var(--space-3)', marginBottom: 'var(--space-4)' }}>
        <div className="form-row" style={{ maxWidth: 280, margin: 0 }}>
          <label>Portfolio</label>
          <select value={name} onChange={(e) => setName(e.target.value)}>
            <option value="">— select —</option>
            {portfolios.map((p) => (
              <option key={p} value={p}>{p}</option>
            ))}
          </select>
        </div>
        <div className="form-row" style={{ maxWidth: 220, margin: 0 }}>
          <label>New name</label>
          <input
            type="text"
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            placeholder="my-portfolio"
          />
        </div>
        <div style={{ display: 'flex', alignItems: 'flex-end', gap: 'var(--space-2)' }}>
          <button type="button" className="btn btn-primary" onClick={onCreate} disabled={creating}>
            Create
          </button>
          {name && (
            <button type="button" className="btn btn-secondary" onClick={onDelete}>
              Delete
            </button>
          )}
        </div>
      </div>

      {summary && (
        <div className="stat-grid">
          <div className="stat-card"><span>Stocks</span><strong>{summary.follow_stocks?.length ?? 0}</strong></div>
          <div className="stat-card"><span>Policies</span><strong>{summary.policies?.length ?? 0}</strong></div>
          <div className="stat-card"><span>Capital</span><strong>{summary.initial_investment ?? '—'}</strong></div>
        </div>
      )}

      {name ? (
        <>
          <textarea className="yaml-editor" value={yaml} onChange={(e) => setYaml(e.target.value)} spellCheck={false} />
          <div style={{ marginTop: 'var(--space-3)' }}>
            <button type="button" className="btn btn-primary" onClick={onSave} disabled={saving || !yaml}>
              Save portfolio
            </button>
          </div>
        </>
      ) : (
        <p style={{ color: 'var(--color-text-muted)' }}>Create a portfolio or select one to edit.</p>
      )}
    </div>
  );
}
