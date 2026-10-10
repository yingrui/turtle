import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { apiFetch } from '../../utils/api';
import { formatCheckedAt } from '../../utils/health';

type HealthState = 'checking' | 'ok' | 'down';

const POLL_MS = 15_000;

/**
 * Quiet API health readout in the header: status dot + time of the last check.
 * Reads `GET /health` (same origin, proxied to the backend in every deploy mode).
 */
export function HealthIndicator() {
  const { t } = useTranslation();
  const [state, setState] = useState<HealthState>('checking');
  const [checkedAt, setCheckedAt] = useState<string | null>(null);

  useEffect(() => {
    let active = true;

    async function check() {
      try {
        await apiFetch<{ status: string }>('/health');
        if (!active) return;
        setState('ok');
      } catch {
        if (!active) return;
        setState('down');
      }
      if (active) setCheckedAt(formatCheckedAt(new Date()));
    }

    check();
    const timer = window.setInterval(check, POLL_MS);
    return () => {
      active = false;
      window.clearInterval(timer);
    };
  }, []);

  const label = t(`header.health.${state}`);

  return (
    <span
      className={`health-chip health-chip--${state}`}
      role="status"
      aria-live="polite"
      title={checkedAt ? t('header.health.checkedAt', { time: checkedAt }) : label}
    >
      <span className="health-chip__dot" aria-hidden />
      <span className="health-chip__label">{label}</span>
      {checkedAt && <span className="health-chip__time">{checkedAt}</span>}
    </span>
  );
}
