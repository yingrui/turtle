import { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../contexts/AuthContext';
import { AppBrand } from '../components/AppBrand';
import { toast } from 'sonner';

export function Register() {
  const { t } = useTranslation();
  const { register } = useAuth();
  const navigate = useNavigate();
  const [loginName, setLoginName] = useState('');
  const [password, setPassword] = useState('');
  const [pending, setPending] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setPending(true);
    try {
      await register(loginName, password);
      navigate('/');
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Registration failed');
    } finally {
      setPending(false);
    }
  }

  return (
    <div className="auth-page">
      <div className="auth-card">
        <AppBrand size="auth" />
        <h1 className="page-title" style={{ marginTop: 0 }}>
          {t('auth.register')}
        </h1>
        <form onSubmit={onSubmit}>
          <div className="form-row">
            <label htmlFor="login">{t('auth.username')}</label>
            <input id="login" value={loginName} onChange={(e) => setLoginName(e.target.value)} required minLength={3} />
          </div>
          <div className="form-row">
            <label htmlFor="password">{t('auth.password')}</label>
            <input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              minLength={6}
            />
          </div>
          <button type="submit" className="btn btn-primary" disabled={pending}>
            {t('auth.register')}
          </button>
        </form>
        <p style={{ marginTop: 'var(--space-4)', fontSize: 'var(--text-sm)' }}>
          <Link to="/login">{t('auth.login')}</Link>
        </p>
      </div>
    </div>
  );
}
