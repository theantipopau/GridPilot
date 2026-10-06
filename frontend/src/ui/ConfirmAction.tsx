import { useState, type ReactNode } from "react";
import { Dialog } from "./Overlay";
import { Button } from "./Button";
import { Input } from "./Input";
import { cx } from "./cx";

interface ConfirmActionProps {
  /** Rendered as the trigger - use a Button/IconButton, not a bare element. */
  children: (props: { open: () => void; busy: boolean }) => ReactNode;
  title: ReactNode;
  /** Spell out the consequence. Approving, rejecting and bulk actions all say
   *  exactly what will happen before it happens. */
  description: ReactNode;
  confirmLabel: string;
  cancelLabel?: string;
  tone?: "primary" | "danger";
  /** Extra friction for multi-record writes: the user must type this string
   *  exactly (the existing bulk-approve contract, unchanged). */
  requirePhrase?: string;
  onConfirm: () => Promise<void> | void;
  className?: string;
}

/** Safe destructive-action confirmation. Replaces the app's window.prompt /
 *  window.alert flow with a real, focus-managed dialog that states the
 *  consequence and keeps confirm disabled until its condition is met. */
export function ConfirmAction({
  children,
  title,
  description,
  confirmLabel,
  cancelLabel = "Cancel",
  tone = "primary",
  requirePhrase,
  onConfirm,
  className,
}: ConfirmActionProps) {
  const [open, setOpen] = useState(false);
  const [typed, setTyped] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const phraseOk = !requirePhrase || typed.trim().toLowerCase() === requirePhrase.trim().toLowerCase();

  const close = () => {
    if (busy) return;
    setOpen(false);
    setTyped("");
    setError(null);
  };

  const confirm = async () => {
    setBusy(true);
    setError(null);
    try {
      await onConfirm();
      setOpen(false);
      setTyped("");
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <span className={cx("inline-flex", className)}>
      {children({ open: () => setOpen(true), busy })}
      <Dialog
        open={open}
        onClose={close}
        busy={busy}
        title={title}
        size="sm"
        footer={
          <>
            <Button size="sm" onClick={close} disabled={busy}>
              {cancelLabel}
            </Button>
            <Button
              size="sm"
              variant={tone === "danger" ? "danger" : "primary"}
              onClick={confirm}
              disabled={!phraseOk}
              loading={busy}
            >
              {confirmLabel}
            </Button>
          </>
        }
      >
        <div className="space-y-3">
          <div className="text-body">{description}</div>
          {requirePhrase && (
            <div>
              <p className="text-meta">
                Type <code className="text-code rounded bg-surface-sunken px-1 py-0.5">{requirePhrase}</code> to
                confirm.
              </p>
              <Input
                value={typed}
                onChange={(e) => setTyped(e.target.value)}
                placeholder={requirePhrase}
                autoComplete="off"
                aria-label={`Type ${requirePhrase} to confirm`}
                className="mt-1.5"
              />
            </div>
          )}
          {error && <p className="text-meta text-critical">{error}</p>}
        </div>
      </Dialog>
    </span>
  );
}
