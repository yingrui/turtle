import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Analyses } from './Analyses';
import { Rankings } from './Rankings';
import './Methods.scss';

/**
 * 选股方法：先看有哪些方法、它们各选出什么；要建新的再展开表单。
 *
 * 之前把表单放在最上面，一进来就是一堆日期和参数，看不出这页是干什么的。列表是主体，新建是次要动作。
 */
export function Methods() {
  const { t } = useTranslation();
  const [building, setBuilding] = useState(false);

  return (
    <div className="methods-page">
      <header className="methods-header">
        <h1>{t('methods.title')}</h1>
        <p className="methods-lead">{t('methods.lead')}</p>
      </header>

      <section className="methods-section" aria-labelledby="methods-list">
        <div className="methods-section-head">
          <h2 id="methods-list">{t('methods.listTitle')}</h2>
          <button type="button" className="btn btn-primary" onClick={() => setBuilding((open) => !open)}>
            {building ? t('methods.cancelBuild') : t('methods.buildTitle')}
          </button>
        </div>
        <p className="methods-hint">{t('methods.listHint')}</p>
        <Rankings embedded />
      </section>

      {building && (
        <section className="methods-section" aria-labelledby="methods-build">
          <h2 id="methods-build">{t('methods.buildTitle')}</h2>
          <p className="methods-hint">{t('methods.buildHint')}</p>
          <Analyses embedded />
        </section>
      )}
    </div>
  );
}
