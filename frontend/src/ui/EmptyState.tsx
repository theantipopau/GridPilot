import type { ReactNode } from "react";
import { cx } from "./cx";

interface EmptyStateProps {
  title: string;
  description?: ReactNode;
  icon?: ReactNode;
  tone?: "neutral" | "positive";
  /** Call to action - empty states in an operational tool usually mean
   *  "here is what to do instead", not just "nothing here". */
  action?: ReactNode;
  className?: string;
}

/** Shared empty/no-results panel. Keep it quiet: an empty queue is a good
 *  outcome, not an error. */
export function EmptyState({ title, description, icon, tone = "neutral", action, className }: EmptyStateProps) {
  return (
    <div
      className={cx(
        "flex flex-col items-center justify-center gap-2 rounded-lg border border-dashed px-6 py-10 text-center",
        tone === "positive"
          ? "border-success-border bg-success-surface text-success"
          : "border-border bg-surface text-text-muted",
        className,
      )}
    >
      {icon && <span aria-hidden="true">{icon}</span>}
      <p className="text-sm font-medium text-text-primary">{title}</p>
      {description && <p className="max-w-sm text-meta">{description}</p>}
      {action && <div className="mt-1">{action}</div>}
    </div>
  );
}
