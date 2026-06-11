import { useTranslation } from 'react-i18next';
import logo from '../assets/logo.svg';

type Props = {
  size?: 'sidebar' | 'auth';
};

export function AppBrand({ size = 'sidebar' }: Props) {
  const { t } = useTranslation();
  const className = size === 'auth' ? 'app-brand-mark' : 'app-sidebar-brand';

  return (
    <div className={className}>
      <img src={logo} alt="" className="app-sidebar-brand-icon" />
      <span className="app-sidebar-brand-title">{t('appName')}</span>
    </div>
  );
}
