import type { ReactNode } from "react";
import { cx } from "./cx";
import type { Tone } from "./Badge";

interface AlertProps {
  tone?: Tone;
  title?: ReactNode;
  children?: ReactNode;
  /** Buttons/links inside the alert (retry, jump to queue). */
  action?: ReactNode;
  onDismiss?: () => void;
  /** "alert" interrupts, "status" is announced politely - errors interrupt. */
  role?: "alert" | "status";
  className?: string;
  icon?: ReactNode;
}  const TONE_CLASS: Record<Tone, string> = {
  neutral: "border-border bg-surface-sunken text-text-secondary",
  info: "border-information-border bg-information-surface text-information",
  success: "border-success-border bg-success-surface text-success",
  warning: "border-warning-border bg-warning-surface text-warning",
  critical: "border-critical-border bg-critical-surface text-critical",
  brand: "border-brand-border bg-brand-surface text-brand",
  accent: "border-accent-border bg-accent-surface text-accent",
};

/** Page/section level message: the single way errors, warnings and success
 *  notes are shown. Body text uses the ink of the tone so contrast is
 *  guaranteed by the token, not by a per-page colour pick. */
export function Alert({ tone = "neutral", title, children, action, onDismiss, role, className, icon }: AlertProps) {
  const resolvedRole = role ?? (tone === "critical" ? "alert" : "status");
  return (
    <div
      role={resolvedRole}
      aria-live={resolvedRole === "alert" ? "assertive" : "polite"}
      className={cx(
        "flex items-start gap-2.5 rounded-lg border px-3.5 py-2.5 text-sm",
        TONE_CLASS[tone],
        className,
      )}
    >
      {icon && (
        <span aria-hidden="true" className="mt-0.5 shrink-0">
          {icon}
        </span>
      )}
      <div className="min-w-0 flex-1 [&_p]:text-current">
        {title && <p className="font-semibold text-current">{title}</p>}
        {children && <div className={cx(title && "mt-0.5", "text-current/85 [&_a]:underline")}>{children}</div>}
      </div>
      {action && <div className="shrink-0">{action}</div>}
      {onDismiss && (
        <button
          type="button"
          onClick={onDismiss}
          aria-label="Dismiss"
          className="-mr-1 shrink-0 rounded px-1 text-current/70 transition-colors duration-150 hover:text-current"
        >
          <svg viewBox="0 0 16 16" className="h-3.5 w-3.5" fill="none" aria-hidden="true">
            <path d="m4 4 8 8M12 4l-8 8" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
          </svg>
        </button>
      )}
    </div>
  );
}
