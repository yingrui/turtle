import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { Analyses } from './Analyses';
import './Datasets.scss';

/** 新建导出：选目标数据集、版本、区间，跑一次任务把 parquet 写进 openKMS。 */
export function DatasetBuild() {
  const { t } = useTranslation();

  return (
    <div className="datasets-page">
      <header className="datasets-header">
        <h1>{t('datasets.buildTitle')}</h1>
        <p className="datasets-lead">{t('datasets.buildLead')}</p>
        <p className="datasets-lead">
          <Link to="/datasets">{t('datasets.backToList')}</Link>
        </p>
      </header>
      <Analyses embedded only="dataset" />
    </div>
  );
}
