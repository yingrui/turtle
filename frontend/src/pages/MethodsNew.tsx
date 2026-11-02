import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { Analyses } from './Analyses';
import './Methods.scss';

/** 第三层：新建评分模型。只做一件事，选完算法填参数就运行。 */
export function MethodsNew() {
  const { t } = useTranslation();

  return (
    <div className="methods-page">
      <header className="methods-header">
        <h1>{t('methods.buildTitle')}</h1>
        <p className="methods-lead">{t('methods.buildHint')}</p>
        <p className="methods-hint">
          <Link to="/methods">{t('methods.backToList')}</Link>
        </p>
      </header>

      <Analyses embedded only="score_table" />
    </div>
  );
}
