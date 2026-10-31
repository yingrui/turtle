import { useTranslation } from 'react-i18next';
import { Analyses } from './Analyses';
import { Rankings } from './Rankings';
import './Methods.scss';

/**
 * One page for "how do I pick stocks": the method that produces a selection, and the selections it has
 * produced. Two routes ("analysis", "ranking sources") forced the user to hold an internal distinction —
 * a computation versus its stored output — that they never act on separately.
 */
export function Methods() {
  const { t } = useTranslation();
  return (
    <div className="methods-page">
      <header className="methods-header">
        <h1>{t('methods.title')}</h1>
        <p className="methods-lead">{t('methods.lead')}</p>
      </header>

      <section className="methods-section" aria-labelledby="methods-build">
        <h2 id="methods-build">{t('methods.buildTitle')}</h2>
        <p className="methods-hint">{t('methods.buildHint')}</p>
        <Analyses embedded />
      </section>

      <section className="methods-section" aria-labelledby="methods-list">
        <h2 id="methods-list">{t('methods.listTitle')}</h2>
        <p className="methods-hint">{t('methods.listHint')}</p>
        <Rankings embedded />
      </section>
    </div>
  );
}
