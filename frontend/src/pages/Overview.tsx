import { useCallback, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { toast } from 'sonner';
import { apiFetch } from '../utils/api';
import './Overview.scss';

type Overview = {
  market_day: string | null;
  portfolio: {
    name: string;
    run_id: string | null;
    run_name: string | null;
    book: { day: string; count: number; market_value: number; cash: number | null; total: number | null } | null;
  } | null;
  alarms: { ts_code: string; reason: string }[];
  methods: { source_id: string; name: string; day: string | null; top: { ts_code: string; score: number }[] }[];
  failed_jobs: number;
};

/** 一屏回答"今天需要你决定什么"。由四块组成，从上到下按"先看什么"排。 */
export function Overview() {
  const { t } = useTranslation();
  const [data, setData] = useState<Overview | null>(null);

  const load = useCallback(async () => {
    try {
      setData(await apiFetch<Overview>('/api/overview'));
    } catch {
      toast.error(t('overview.loadFailed'));
    }
  }, [t]);

  useEffect(() => {
    void load();
  }, [load]);

  const book = data?.portfolio?.book ?? null;

  return (
    <div className="overview-page">
      <h1>{t('overview.title')}</h1>

      <section className="overview-block">
        <h2>{t('overview.dataTitle')}</h2>
        <p className="overview-line">
          {t('overview.dataLine', { day: data?.market_day ?? '—' })}
        </p>
      </section>

      <section className="overview-block">
        <h2>{t('overview.bookTitle')}</h2>
        {book ? (
          <>
            <p className="overview-line">
              {t('overview.bookLine', {
                name: data?.portfolio?.name ?? '',
                run: data?.portfolio?.run_name ?? '',
                day: book.day,
                count: book.count,
              })}
            </p>
            <p className="overview-line">
              {t('overview.bookValue', {
                value: book.market_value.toLocaleString(undefined, { maximumFractionDigits: 0 }),
                cash: book.cash == null ? '—' : book.cash.toLocaleString(undefined, { maximumFractionDigits: 0 }),
                total: book.total == null ? '—' : book.total.toLocaleString(undefined, { maximumFractionDigits: 0 }),
              })}
            </p>
            <p className="overview-line">
              <Link to="/portfolio?tab=holdings">{t('overview.openHoldings')}</Link>
            </p>
          </>
        ) : (
          <p className="overview-line">
            {t('overview.noBook')} <Link to="/simulation/new">{t('overview.startRun')}</Link>
          </p>
        )}
      </section>

      <section className="overview-block">
        <h2>{t('overview.alarmTitle')}</h2>
        {data && data.alarms.length > 0 ? (
          <ul className="overview-list">
            {data.alarms.slice(0, 10).map((alarm) => (
              <li key={alarm.ts_code}>
                {alarm.ts_code} — {alarm.reason === 'out_of_pool' ? t('overview.reasonOutOfPool') : alarm.reason}
              </li>
            ))}
          </ul>
        ) : (
          <p className="overview-line">{t('overview.noAlarm')}</p>
        )}
      </section>

      <section className="overview-block">
        <h2>{t('overview.methodsTitle')}</h2>
        {data && data.methods.length > 0 ? (
          <ul className="overview-list">
            {data.methods.map((method) => (
              <li key={method.source_id}>
                <Link to={`/methods/${method.source_id}`}>{method.name}</Link>
                {method.top.length > 0 && (
                  <span className="overview-picks">
                    {method.top.map((pick) => pick.ts_code).join(' · ')}
                  </span>
                )}
              </li>
            ))}
          </ul>
        ) : (
          <p className="overview-line">
            {t('overview.noMethod')} <Link to="/methods">{t('overview.createMethod')}</Link>
          </p>
        )}
      </section>

      {data && data.failed_jobs > 0 && (
        <section className="overview-block">
          <h2>{t('overview.todoTitle')}</h2>
          <p className="overview-line">
            {t('overview.failedJobs', { count: data.failed_jobs })} <Link to="/jobs">{t('overview.openJobs')}</Link>
          </p>
        </section>
      )}
    </div>
  );
}
