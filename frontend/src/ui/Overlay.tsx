import { useId, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { cx } from "./cx";
import { IconButton } from "./Button";
import { useFocusTrap, useScrollLock } from "./useFocusTrap";

interface DialogProps {
  open: boolean;
  onClose: () => void;
  title: ReactNode;
  description?: ReactNode;
  children?: ReactNode;
  footer?: ReactNode;
  size?: "sm" | "md" | "lg";
  /** Blocks Escape/overlay dismissal while a request is in flight. */
  busy?: boolean;
}

const DIALOG_SIZE: Record<NonNullable<DialogProps["size"]>, string> = {
  sm: "max-w-sm",
  md: "max-w-lg",
  lg: "max-w-2xl",
};

/** Modal dialog: scrim, focus trap, Escape, labelled by its own title.
 *  Destructive confirmations go through ConfirmAction, which uses this. */
export function Dialog({ open, onClose, title, description, children, footer, size = "md", busy }: DialogProps) {
  const titleId = useId();
  const descId = useId();
  const trapRef = useFocusTrap(open, busy ? undefined : onClose);
  useScrollLock(open);

  if (!open) return null;

  return createPortal(
    <div
      className="fixed inset-0 z-50 flex animate-fade-in items-start justify-center overflow-y-auto bg-scrim px-4 py-[10vh] backdrop-blur-[2px]"
      onPointerDown={(e) => {
        if (e.target === e.currentTarget && !busy) onClose();
      }}
    >
      <div
        ref={trapRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        aria-describedby={description ? descId : undefined}
        tabIndex={-1}
        className={cx(
          "w-full rounded-xl border border-border bg-surface-elevated shadow-2xl animate-panel-in",
          DIALOG_SIZE[size],
        )}
      >
        <div className="flex items-start justify-between gap-4 border-b border-border px-5 py-3.5">
          <div className="min-w-0">
            <h2 id={titleId} className="text-section-title">
              {title}
            </h2>
            {description && (
              <p id={descId} className="mt-0.5 text-meta">
                {description}
              </p>
            )}
          </div>
          {!busy && (
            <IconButton
              label="Close"
              size="sm"
              className="-mr-1.5 -mt-1"
              onClick={onClose}
              icon={
                <svg viewBox="0 0 16 16" className="h-4 w-4" fill="none" aria-hidden="true">
                  <path d="m4 4 8 8M12 4l-8 8" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
                </svg>
              }
            />
          )}
        </div>
        {children != null && <div className="px-5 py-4 text-sm text-text-secondary">{children}</div>}
        {footer && <div className="flex justify-end gap-2 border-t border-border px-5 py-3">{footer}</div>}
      </div>
    </div>,
    document.body,
  );
}

interface DrawerProps {
  open: boolean;
  onClose: () => void;
  title: ReactNode;
  subtitle?: ReactNode;
  /** Rendered beside the title - status badges for the inspected entity. */
  meta?: ReactNode;
  children: ReactNode;
  footer?: ReactNode;
  width?: "narrow" | "wide";
  /** Optional scrim. The timetable inspector keeps the grid visible, so it
   *  passes null; heavier flows dim the page behind. */
  scrim?: "none" | "soft";
}

/** Side panel for detail inspection. Same focus contract as Dialog, but it
 *  must not swallow the page: Escape and focus restoration still apply, and
 *  the trigger (grid cell, row) is where focus returns. */
export function Drawer({
  open,
  onClose,
  title,
  subtitle,
  meta,
  children,
  footer,
  width = "narrow",
  scrim = "soft",
}: DrawerProps) {
  const titleId = useId();
  const trapRef = useFocusTrap(open, onClose);

  if (!open) return null;

  return createPortal(
    <>
      {scrim === "soft" && (
        <div className="fixed inset-0 z-40 animate-fade-in bg-scrim" onPointerDown={onClose} aria-hidden="true" />
      )}
      <aside
        ref={trapRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        tabIndex={-1}
        className={cx(
          "fixed inset-y-0 right-0 z-40 flex animate-slide-in-right flex-col border-l border-border bg-surface-elevated shadow-2xl",
          width === "wide" ? "w-full max-w-120" : "w-full max-w-96",
        )}
      >
        <header className="flex items-start justify-between gap-3 border-b border-border px-5 py-4">
          <div className="min-w-0 flex-1">
            <h2 id={titleId} className="truncate text-section-title">
              {title}
            </h2>
            {subtitle && <p className="mt-0.5 truncate text-meta">{subtitle}</p>}
            {meta && <div className="mt-2 flex flex-wrap items-center gap-1.5">{meta}</div>}
          </div>
          <IconButton
            label="Close panel"
            size="sm"
            className="-mr-1.5 -mt-1 shrink-0"
            onClick={onClose}
            icon={
              <svg viewBox="0 0 16 16" className="h-4 w-4" fill="none" aria-hidden="true">
                <path d="m4 4 8 8M12 4l-8 8" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
              </svg>
            }
          />
        </header>
        <div className="min-h-0 flex-1 overflow-y-auto px-5 py-4">{children}</div>
        {footer && <div className="border-t border-border px-5 py-3">{footer}</div>}
      </aside>
    </>,
    document.body,
  );
}
