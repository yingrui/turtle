import { useEffect, useRef, useState } from 'react';
import { LogOut } from 'lucide-react';
import { useTranslation } from 'react-i18next';

type UserMenuProps = {
  user: { login: string; is_admin: boolean } | null;
  onLogout: () => void;
};

function userInitials(login: string): string {
  const parts = login.trim().split(/[._-]/).filter(Boolean);
  if (parts.length >= 2) {
    return (parts[0][0] + parts[1][0]).toUpperCase();
  }
  return login.slice(0, 2).toUpperCase();
}

export function UserMenu({ user, onLogout }: UserMenuProps) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    function onPointerDown(e: MouseEvent) {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener('mousedown', onPointerDown);
    return () => document.removeEventListener('mousedown', onPointerDown);
  }, [open]);

  if (!user) return null;

  return (
    <div className={`user-menu${open ? ' user-menu--open' : ''}`} ref={rootRef}>
      <button
        type="button"
        className="user-menu__trigger"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        aria-haspopup="menu"
        aria-label={user.login}
      >
        <span className="user-menu__avatar" aria-hidden>
          {userInitials(user.login)}
        </span>
      </button>
      {open && (
        <div className="user-menu__dropdown" role="menu">
          <div className="user-menu__profile">
            <span className="user-menu__avatar user-menu__avatar--lg" aria-hidden>
              {userInitials(user.login)}
            </span>
            <div className="user-menu__meta">
              <strong>{user.login}</strong>
              {user.is_admin && <span className="user-menu__badge">{t('header.admin')}</span>}
            </div>
          </div>
          <button
            type="button"
            className="user-menu__item"
            role="menuitem"
            onClick={() => {
              setOpen(false);
              onLogout();
            }}
          >
            <LogOut size={16} />
            <span>{t('auth.logout')}</span>
          </button>
        </div>
      )}
    </div>
  );
}
