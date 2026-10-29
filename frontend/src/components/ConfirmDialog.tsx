import { useTranslation } from 'react-i18next';
import { Dialog } from './Dialog';

type Props = {
  open: boolean;
  title: string;
  message: string;
  confirmLabel?: string;
  onConfirm: () => void;
  onCancel: () => void;
  busy?: boolean;
};

/**
 * `window.confirm` blocks the whole tab, cannot be styled or translated consistently, and its buttons
 * say whatever the browser's language says. This is the same question asked with the app's `<Dialog>`,
 * so it inherits focus handling and `Esc`.
 */
export function ConfirmDialog({
  open,
  title,
  message,
  confirmLabel,
  onConfirm,
  onCancel,
  busy = false,
}: Props) {
  const { t } = useTranslation();
  return (
    <Dialog
      open={open}
      title={title}
      onClose={onCancel}
      footer={
        <div className="dialog-actions">
          <button type="button" className="btn btn-secondary" onClick={onCancel} disabled={busy}>
            {t('screening.cancel')}
          </button>
          <button type="button" className="btn btn-primary" onClick={onConfirm} disabled={busy}>
            {confirmLabel ?? t('common.confirm')}
          </button>
        </div>
      }
    >
      <p className="text-sm">{message}</p>
    </Dialog>
  );
}
