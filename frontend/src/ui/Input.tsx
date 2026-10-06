import { forwardRef, useId, type InputHTMLAttributes, type ReactNode } from "react";
import { cx } from "./cx";

export type FieldSize = "sm" | "md";

interface FieldShellProps {
  id: string;
  label?: string;
  hint?: string;
  error?: string;
  required?: boolean;
  className?: string;
  children: ReactNode;
}

/** Label + control + hint/error with the wiring done once: every input in the
 *  app gets a programmatic label and a described-by hint/error, which is the
 *  single most common a11y gap the audit found. */
export function FieldShell({ id, label, hint, error, required, className, children }: FieldShellProps) {
  return (
    <div className={cx("flex flex-col gap-1", className)}>
      {label && (
        <label htmlFor={id} className="text-label">
          {label}
          {required && (
            <span className="ml-1 text-critical" aria-hidden="true">
              *
            </span>
          )}
        </label>
      )}
      {children}
      {error ? (
        <p id={`${id}-error`} className="text-meta text-critical">
          {error}
        </p>
      ) : hint ? (
        <p id={`${id}-hint`} className="text-meta">
          {hint}
        </p>
      ) : null}
    </div>
  );
}

const CONTROL_CLASS =
  "w-full rounded-md border bg-surface text-sm text-text-primary placeholder:text-text-muted " +
  "transition-[border-color,box-shadow] duration-150 ease-[var(--ease-out-quart)] " +
  "disabled:cursor-not-allowed disabled:bg-surface-sunken disabled:text-text-muted " +
  "read-only:bg-surface-sunken";

const SIZE_CLASS: Record<FieldSize, string> = {
  sm: "h-7 px-2 text-xs",
  md: "h-8.5 px-2.5 text-sm",
};

function controlTone(error?: string): string {
  return error
    ? "border-critical hover:border-critical focus:border-critical"
    : "border-border-strong hover:border-border-strong/80";
}

export interface InputProps extends Omit<InputHTMLAttributes<HTMLInputElement>, "size"> {
  label?: string;
  hint?: string;
  error?: string;
  size?: FieldSize;
  prefixIcon?: ReactNode;
  containerClassName?: string;
}

export const Input = forwardRef<HTMLInputElement, InputProps>(function Input(
  { label, hint, error, size = "md", prefixIcon, containerClassName, className, id, required, ...rest },
  ref,
) {
  const autoId = useId();
  const inputId = id ?? autoId;
  const describedBy = error ? `${inputId}-error` : hint ? `${inputId}-hint` : undefined;

  return (
    <FieldShell id={inputId} label={label} hint={hint} error={error} required={required} className={containerClassName}>
      <div className="relative">
        {prefixIcon && (
          <span className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-text-muted">
            {prefixIcon}
          </span>
        )}
        <input
          ref={ref}
          id={inputId}
          required={required}
          aria-invalid={error ? true : undefined}
          aria-describedby={describedBy}
          className={cx(
            CONTROL_CLASS,
            SIZE_CLASS[size],
            prefixIcon && "pl-8",
            controlTone(error),
            "focus:border-focus focus:outline-none focus-visible:outline-none",
            "focus:shadow-[0_0_0_3px_color-mix(in_oklab,var(--color-focus)_22%,transparent)]",
            className,
          )}
          {...rest}
        />
      </div>
    </FieldShell>
  );
});

export interface SearchInputProps {
  value: string;
  onChange: (value: string) => void;
  placeholder: string;
  resultCount?: number;
  totalCount?: number;
  size?: FieldSize;
  className?: string;
  id?: string;
  /** Accessible name when no visible label is rendered. */
  label?: string;
}

/** The one search field for local, client-side list filtering. Shows how much
 *  of the list survived the filter so a narrow result never reads as data loss. */
export function SearchInput({
  value,
  onChange,
  placeholder,
  resultCount,
  totalCount,
  size = "md",
  className,
  id,
  label = "Search",
}: SearchInputProps) {
  const autoId = useId();
  const inputId = id ?? autoId;
  const showCount = resultCount != null && totalCount != null && value.trim().length > 0;

  return (
    <div className={cx("flex items-center gap-2", className)}>
      <div className="relative">
        <span className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-text-muted">
          <SearchGlyph />
        </span>
        <input
          id={inputId}
          type="search"
          aria-label={label}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={placeholder}
          className={cx(
            CONTROL_CLASS,
            SIZE_CLASS[size],
            "pl-8 pr-7 [&::-webkit-search-cancel-button]:hidden",
            controlTone(),
            "focus:border-focus focus:outline-none focus:shadow-[0_0_0_3px_color-mix(in_oklab,var(--color-focus)_22%,transparent)]",
          )}
        />
        {value && (
          <button
            type="button"
            onClick={() => onChange("")}
            aria-label="Clear search"
            className="absolute right-1.5 top-1/2 flex h-5 w-5 -translate-y-1/2 items-center justify-center rounded text-text-muted transition-colors duration-150 hover:bg-surface-muted hover:text-text-primary"
          >
            <CloseGlyph />
          </button>
        )}
      </div>
      {showCount && (
        <span className="nums whitespace-nowrap text-meta" aria-live="polite">
          {resultCount} of {totalCount}
        </span>
      )}
    </div>
  );
}

function SearchGlyph() {
  return (
    <svg viewBox="0 0 16 16" className="h-3.5 w-3.5" fill="none" aria-hidden="true">
      <circle cx="7" cy="7" r="4.5" stroke="currentColor" strokeWidth="1.5" />
      <path d="m10.5 10.5 3 3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  );
}

function CloseGlyph() {
  return (
    <svg viewBox="0 0 16 16" className="h-3 w-3" fill="none" aria-hidden="true">
      <path d="m4 4 8 8M12 4l-8 8" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  );
}
