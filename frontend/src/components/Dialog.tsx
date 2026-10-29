import { useEffect, useRef, type ReactNode } from 'react';
import './Dialog.scss';

type Props = {
  open: boolean;
  title: string;
  onClose: () => void;
  children: ReactNode;
  /** Buttons for the bottom row (usually Cancel + primary action). */
  footer?: ReactNode;
};

/**
 * The app's modal. Native `<dialog>` gives the behaviour that hand-rolled overlays forget: focus moves
 * into the dialog and is trapped there, `Esc` closes it, the page behind becomes inert, and screen
 * readers announce it as a dialog with the given title.
 *
 * Three pages used to build their own overlay `<div>`; each one had a different backdrop colour and
 * none handled `Esc`.
 */
export function Dialog({ open, title, onClose, children, footer }: Props) {
  const ref = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    const element = ref.current;
    if (!element) return;
    // jsdom (the test environment) does not implement showModal; the markup still renders.
    if (open && typeof element.showModal === 'function' && !element.open) {
      element.showModal();
    } else if (!open && typeof element.close === 'function' && element.open) {
      element.close();
    }
  }, [open]);

  if (!open) return null;

  return (
    <dialog
      ref={ref}
      className="ds-dialog"
      aria-label={title}
      onClose={onClose}
      // A click on the backdrop lands on the <dialog> element itself, not the inner panel.
      onClick={(event) => {
        if (event.target === ref.current) onClose();
      }}
    >
      <div className="ds-dialog__panel">
        <h2 className="ds-dialog__title">{title}</h2>
        <div className="ds-dialog__body">{children}</div>
        {footer ? <div className="ds-dialog__footer">{footer}</div> : null}
      </div>
    </dialog>
  );
}
