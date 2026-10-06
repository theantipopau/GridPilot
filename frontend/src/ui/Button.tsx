import type { ButtonHTMLAttributes, ReactNode } from "react";
import { cx } from "./cx";

export type ButtonVariant = "primary" | "secondary" | "ghost" | "accent" | "danger";
export type ButtonSize = "sm" | "md";

interface ButtonBase {
  variant?: ButtonVariant;
  size?: ButtonSize;
  /** Swaps the label for a spinner, sets aria-busy and blocks the click -
   *  every mutating action in the app gets a v100-150ms honest "working"
   *  state instead of firing twice. */
  loading?: boolean;
  iconLeft?: ReactNode;
  iconRight?: ReactNode;
  block?: boolean;
}

export type ButtonProps = ButtonBase & ButtonHTMLAttributes<HTMLButtonElement>;

const VARIANT_CLASS: Record<ButtonVariant, string> = {
  primary:
    "bg-brand text-brand-contrast border border-transparent shadow-sm hover:bg-brand-strong active:bg-brand-strong",
  secondary:
    "bg-surface text-text-secondary border border-border-strong hover:bg-hovered hover:text-text-primary",
  ghost: "bg-transparent text-text-secondary border border-transparent hover:bg-hovered hover:text-text-primary",
  accent:
    "bg-accent text-white border border-transparent shadow-sm hover:brightness-95 active:brightness-95",
  danger:
    "bg-critical text-white border border-transparent shadow-sm hover:bg-critical-strong active:bg-critical-strong",
};

const SIZE_CLASS: Record<ButtonSize, string> = {
  sm: "h-7 px-2.5 text-xs gap-1 rounded-md",
  md: "h-8.5 px-3 text-sm gap-1.5 rounded-md",
};

export function Button({
  variant = "secondary",
  size = "md",
  loading = false,
  iconLeft,
  iconRight,
  block,
  className,
  children,
  disabled,
  type = "button",
  ...rest
}: ButtonProps) {
  return (
    <button
      type={type}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      className={cx(
        "inline-flex select-none items-center justify-center font-medium transition-[background-color,border-color,color,box-shadow,opacity,transform] duration-150 ease-[var(--ease-out-quart)]",
        "disabled:cursor-not-allowed disabled:opacity-55",
        "enabled:active:scale-[0.98]",
        VARIANT_CLASS[variant],
        SIZE_CLASS[size],
        block && "w-full",
        className,
      )}
      {...rest}
    >
      {loading ? <Spinner /> : iconLeft}
      {children != null && <span className="truncate">{children}</span>}
      {!loading && iconRight}
    </button>
  );
}

interface IconButtonProps extends Omit<ButtonHTMLAttributes<HTMLButtonElement>, "children" | "aria-label"> {
  /** Required: an icon-only control with no accessible name is unusable. */
  label: string;
  icon: ReactNode;
  variant?: ButtonVariant;
  size?: ButtonSize;
  loading?: boolean;
  /** Renders the label visibly next to the icon (sidebar collapse toggle). */
  showLabel?: boolean;
}

const ICON_SIZE_CLASS: Record<ButtonSize, string> = {
  sm: "h-7 w-7 rounded-md",
  md: "h-8.5 w-8.5 rounded-md",
};

export function IconButton({
  label,
  icon,
  variant = "ghost",
  size = "md",
  loading = false,
  showLabel = false,
  className,
  disabled,
  type = "button",
  ...rest
}: IconButtonProps) {
  return (
    <button
      type={type}
      aria-label={showLabel ? undefined : label}
      title={showLabel ? undefined : label}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      className={cx(
        "inline-flex items-center justify-center gap-1.5 font-medium transition-[background-color,border-color,color,box-shadow,opacity,transform] duration-150 ease-[var(--ease-out-quart)]",
        "disabled:cursor-not-allowed disabled:opacity-55",
        "enabled:active:scale-[0.97]",
        VARIANT_CLASS[variant],
        showLabel ? "h-8.5 px-2.5 text-sm rounded-md" : ICON_SIZE_CLASS[size],
        className,
      )}
      {...rest}
    >
      {loading ? <Spinner /> : icon}
      {showLabel && <span className="truncate">{label}</span>}
    </button>
  );
}

function Spinner() {
  return (
    <svg viewBox="0 0 16 16" aria-hidden="true" className="h-3.5 w-3.5 animate-spin">
      <circle cx="8" cy="8" r="6" fill="none" stroke="currentColor" strokeOpacity="0.25" strokeWidth="2.5" />
      <path
        d="M14 8a6 6 0 0 0-6-6"
        fill="none"
        stroke="currentColor"
        strokeWidth="2.5"
        strokeLinecap="round"
      />
    </svg>
  );
}
