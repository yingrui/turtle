import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { CalendarClock } from 'lucide-react';
import { apiFetch } from '../../utils/api';

type DataStatus = { as_of_date: string | null };

type Level = 'ok' | 'stale' | 'missing';

function levelFor(asOf: string | null): Level {
  if (!asOf) return 'missing';
  const asOfDate = new Date(`${asOf}T00:00:00`);
  const today = new Date();
  const businessDays = Math.floor((today.getTime() - asOfDate.getTime()) / 86_400_000 / 7) * 5;
  const rough = (today.getTime() - asOfDate.getTime()) / 86_400_000;
  // Anything more than a long weekend behind is worth flagging.
  return rough > 4 || businessDays > 3 ? 'stale' : 'ok';
}

/**
 * Always-visible data freshness. The app reads market data written by an external ETL, so every
 * screen needs to say "as of when" — this is that one place.
 */
export function DataFreshnessChip() {
  const { t } = useTranslation();
  const [asOf, setAsOf] = useState<string | null>(null);

  useEffect(() => {
    apiFetch<DataStatus>('/api/data/status')
      .then((d) => setAsOf(d.as_of_date ?? null))
      .catch(() => setAsOf(null));
  }, []);

  const level = levelFor(asOf);
  return (
    <Link
      to="/data"
      className={`header-chip header-chip--${level}`}
      title={t('header.dataFreshness')}
    >
      <CalendarClock size={14} />
      <span>{asOf ? `${t('header.dataAsOf')} ${asOf}` : t('header.dataMissing')}</span>
    </Link>
  );
}
