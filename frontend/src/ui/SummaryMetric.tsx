import type { ReactNode } from "react";
import { cx } from "./cx";
import type { Tone } from "./Badge";

const TONE_TEXT: Record<Tone, string> = {
  neutral: "text-text-primary",
  info: "text-information",
  success: "text-success",
  warning: "text-warning",
  critical: "text-critical",
  brand: "text-brand",
  accent: "text-accent",
};

export interface SummaryMetricProps {
  label: string;
  value: ReactNode;
  /** Unit or suffix shown beside the value ("%", "of 75"). */
  suffix?: string;
  tone?: Tone;
  hint?: string;
  icon?: ReactNode;
  /** Makes the whole metric a button when it navigates to the underlying list. */
  onClick?: () => void;
  /** Emphasises the value without inflating the type size. */
  emphasis?: boolean;
  className?: string;
}

/** One restrained metric: label, number, optional context. Deliberately not a
 *  decorative card - the dashboard's job is operational status, so metrics sit
 *  in a quiet strip rather than a grid of large tiles. Tabular numerals are
 *  applied so columns of counts line up. */
export function SummaryMetric({
  label,
  value,
  suffix,
  tone = "neutral",
  hint,
  icon,
  onClick,
  emphasis,
  className,
}: SummaryMetricProps) {
  const body = (
    <>
      <span className="flex items-center gap-1.5 text-label truncate">
        {icon && <span aria-hidden="true" className="text-text-muted">{icon}</span>}
        <span className="truncate">{label}</span>
      </span>
      <span className="flex items-baseline gap-1">
        <span className={cx("nums font-semibold tracking-tight", emphasis ? "text-2xl" : "text-xl", TONE_TEXT[tone])}>
          {value}
        </span>
        {suffix && <span className="nums text-meta">{suffix}</span>}
      </span>
      {hint && <span className="truncate text-meta">{hint}</span>}
    </>
  );

  if (onClick) {
    return (
      <button
        type="button"
        onClick={onClick}
        className={cx(
          "group flex min-w-0 flex-col gap-1 rounded-lg border border-border bg-surface px-3.5 py-3 text-left",
          "transition-[border-color,background-color,box-shadow] duration-150 ease-[var(--ease-out-quart)]",
          "hover:border-border-strong hover:bg-hovered focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus",
          className,
        )}
      >
        {body}
      </button>
    );
  }

  return <div className={cx("flex min-w-0 flex-col gap-1 rounded-lg border border-border bg-surface px-3.5 py-3", className)}>{body}</div>;
}
