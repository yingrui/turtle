import { useEffect, useRef, useState } from 'react';
import { LogOut } from 'lucide-react';
import { useTranslation } from 'react-i18next';

type UserMenuProps = {
  user: { login: string; is_admin: boolean; name?: string | null } | null;
  onLogout: () => void;
  /** When false (STOCK_AUTH_MODE=none), hide logout — host owns the session. */
  showLogout?: boolean;
};

function displayName(user: { login: string; name?: string | null }): string {
  return (user.name || user.login).trim() || user.login;
}

function userInitials(label: string): string {
  const parts = label.trim().split(/[._\s-]/).filter(Boolean);
  if (parts.length >= 2) {
    return (parts[0][0] + parts[1][0]).toUpperCase();
  }
  return label.slice(0, 2).toUpperCase();
}

export function UserMenu({ user, onLogout, showLogout = true }: UserMenuProps) {
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

  const label = displayName(user);

  return (
    <div className={`user-menu${open ? ' user-menu--open' : ''}`} ref={rootRef}>
      <button
        type="button"
        className="user-menu__trigger"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        aria-haspopup="menu"
        aria-label={label}
      >
        <span className="user-menu__avatar" aria-hidden>
          {userInitials(label)}
        </span>
      </button>
      {open && (
        <div className="user-menu__dropdown" role="menu">
          <div className="user-menu__profile">
            <span className="user-menu__avatar user-menu__avatar--lg" aria-hidden>
              {userInitials(label)}
            </span>
            <div className="user-menu__meta">
              <strong>{label}</strong>
              {user.login !== label && <span className="user-menu__badge">{user.login}</span>}
              {user.is_admin && <span className="user-menu__badge">{t('header.admin')}</span>}
            </div>
          </div>
          {showLogout && (
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
          )}
        </div>
      )}
    </div>
  );
}
