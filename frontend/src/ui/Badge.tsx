import type { ReactNode } from "react";
import { cx } from "./cx";

/** Semantic tone shared by every status surface in the app. A tone always
 *  carries BOTH a colour and a word/icon - status is never colour-alone. */
export type Tone = "neutral" | "info" | "success" | "warning" | "critical" | "brand" | "accent";

export type BadgeVariant = "soft" | "solid" | "outline";

interface BadgeProps {
  tone?: Tone;
  variant?: BadgeVariant;
  size?: "sm" | "md";
  children: ReactNode;
  /** Paired glyph - use wherever the badge is the only status signal. */
  icon?: ReactNode;
  className?: string;
  title?: string;
}

const SOFT_CLASS: Record<Tone, string> = {
  neutral: "bg-surface-sunken text-text-secondary border-border",
  info: "bg-information-surface text-information border-information-border",
  success: "bg-success-surface text-success border-success-border",
  warning: "bg-warning-surface text-warning border-warning-border",
  critical: "bg-critical-surface text-critical border-critical-border",
  brand: "bg-brand-surface text-brand border-brand-border",
  accent: "bg-accent-surface text-accent border-accent-border",
};

const SOLID_CLASS: Record<Tone, string> = {
  neutral: "bg-text-secondary text-surface border-transparent",
  info: "bg-information text-white border-transparent",
  success: "bg-success text-white border-transparent",
  warning: "bg-warning text-white border-transparent",
  critical: "bg-critical text-white border-transparent",
  brand: "bg-brand text-brand-contrast border-transparent",
  accent: "bg-accent text-white border-transparent",
};

const OUTLINE_CLASS: Record<Tone, string> = {
  neutral: "bg-transparent text-text-secondary border-border-strong",
  info: "bg-transparent text-information border-information-border",
  success: "bg-transparent text-success border-success-border",
  warning: "bg-transparent text-warning border-warning-border",
  critical: "bg-transparent text-critical border-critical-border",
  brand: "bg-transparent text-brand border-brand-border",
  accent: "bg-transparent text-accent border-accent-border",
};

export function Badge({ tone = "neutral", variant = "soft", size = "md", icon, children, className, title }: BadgeProps) {
  const toneClass =
    variant === "solid" ? SOLID_CLASS[tone] : variant === "outline" ? OUTLINE_CLASS[tone] : SOFT_CLASS[tone];

  return (
    <span
      title={title}
      className={cx(
        "inline-flex max-w-full items-center gap-1 border font-medium whitespace-nowrap align-middle",
        size === "sm" ? "rounded px-1.5 py-px text-[11px] leading-4" : "rounded-full px-2 py-0.5 text-xs leading-4.5",
        toneClass,
        className,
      )}
    >
      {icon}
      <span className="truncate">{children}</span>
    </span>
  );
}

export interface StatusIndicatorProps {
  tone: Tone;
  label: ReactNode;
  /** Explicit glyph. Defaults to a filled dot, which is only acceptable when
   *  the label sits immediately beside it (it always does here). */
  icon?: ReactNode;
  size?: "sm" | "md";
  className?: string;
  title?: string;
}

/** Inline status: glyph + word. Used where a colour fill would be too heavy
 *  (table cells, dense rows, list metadata) but colour-alone would be opaque. */
export function StatusIndicator({ tone, label, icon, size = "md", className, title }: StatusIndicatorProps) {
  return (
    <span
      title={title}
      className={cx(
        "inline-flex max-w-full items-center gap-1.5 font-medium",
        size === "sm" ? "text-[11px]" : "text-xs",
        TEXT_TONE[tone],
        className,
      )}
    >
      {icon ?? <span aria-hidden="true" className={cx("h-2 w-2 shrink-0 rounded-full", DOT_TONE[tone])} />}
      <span className="truncate">{label}</span>
    </span>
  );
}

const TEXT_TONE: Record<Tone, string> = {
  neutral: "text-text-secondary",
  info: "text-information",
  success: "text-success",
  warning: "text-warning",
  critical: "text-critical",
  brand: "text-brand",
  accent: "text-accent",
};

const DOT_TONE: Record<Tone, string> = {
  neutral: "bg-text-muted",
  info: "bg-information",
  success: "bg-success",
  warning: "bg-warning",
  critical: "bg-critical",
  brand: "bg-brand",
  accent: "bg-accent",
};
