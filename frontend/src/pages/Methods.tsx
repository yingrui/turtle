import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { Rankings } from './Rankings';
import './Methods.scss';

/**
 * 第一层：只列有哪些评分模型。明细在行内展开，新建在单独一页 —— 一屏只回答一个问题。
 */
export function Methods() {
  const { t } = useTranslation();

  return (
    <div className="methods-page">
      <header className="methods-header">
        <h1>{t('methods.title')}</h1>
        <p className="methods-lead">{t('methods.lead')}</p>
      </header>

      <div className="methods-section-head">
        <h2>{t('methods.listTitle')}</h2>
        <Link className="btn btn-primary" to="/methods/new">
          {t('methods.buildTitle')}
        </Link>
      </div>
      <p className="methods-hint">{t('methods.listHint')}</p>

      <Rankings embedded />
    </div>
  );
}
