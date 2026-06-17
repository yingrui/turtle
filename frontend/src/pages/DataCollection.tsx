import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { toast } from 'sonner';
import { apiFetch } from '../utils/api';

type TableStatus = {
  name: string;
  latest_trade_date: string | null;
  row_count?: number | null;
};

type DataStatus = {
  as_of_date: string | null;
  source: string;
  tables: TableStatus[];
};

export function DataCollection() {
  const { t } = useTranslation();
  const [status, setStatus] = useState<DataStatus | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    apiFetch<DataStatus>('/api/data/status')
      .then(setStatus)
      .catch(() => toast.error(t('data.status.loadError')))
      .finally(() => setLoading(false));
  }, [t]);

  return (
    <div className="page-card">
      <h1 className="page-title">{t('nav.data')}</h1>
      <p style={{ color: 'var(--color-text-muted)', marginBottom: 'var(--space-4)' }}>
        {t('data.status.description')}
      </p>

      {loading && <p>{t('data.status.loading')}</p>}

      {!loading && status && (
        <>
          <p style={{ marginBottom: 'var(--space-4)' }}>
            {t('data.status.asOf')}: <strong>{status.as_of_date ?? '—'}</strong>
            {' · '}
            {t('data.status.source')}: {status.source}
          </p>
          <table className="data-table">
            <thead>
              <tr>
                <th>{t('data.status.table')}</th>
                <th>{t('data.status.latestDate')}</th>
                <th>{t('data.status.rowCount')}</th>
              </tr>
            </thead>
            <tbody>
              {status.tables.map((row) => (
                <tr key={row.name}>
                  <td><code>{row.name}</code></td>
                  <td>{row.latest_trade_date ?? '—'}</td>
                  <td>{row.row_count != null ? row.row_count.toLocaleString() : '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {!status.as_of_date && (
            <p className="error-banner" style={{ marginTop: 'var(--space-4)' }}>
              {t('data.status.empty')}
            </p>
          )}
          <p style={{ marginTop: 'var(--space-4)', fontSize: 'var(--text-sm)', color: 'var(--color-text-muted)' }}>
            {t('data.status.etlHint')}{' '}
            <Link to="/screening">{t('nav.screening')}</Link>
          </p>
        </>
      )}
    </div>
  );
}
