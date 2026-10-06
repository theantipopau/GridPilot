import { useId, type InputHTMLAttributes, type ReactNode } from "react";
import { cx } from "./cx";

export interface CheckboxProps extends Omit<InputHTMLAttributes<HTMLInputElement>, "type" | "size"> {
  label: ReactNode;
  hint?: string;
  /** Mixed state for "some rows in this group are selected". */
  indeterminate?: boolean;
}

/** Native checkbox with a real label - the box is the only place the app's
 *  bulk-selection affordances appear, so it stays a genuine form control. */
export function Checkbox({ label, hint, indeterminate, id, className, ...rest }: CheckboxProps) {
  const autoId = useId();
  const inputId = id ?? autoId;
  const describedBy = hint ? `${inputId}-hint` : undefined;

  return (
    <div className={cx("flex items-start gap-2", className)}>
      <input
        ref={(el) => {
          if (el) el.indeterminate = !!indeterminate;
        }}
        id={inputId}
        type="checkbox"
        aria-describedby={describedBy}
        className={cx(
          "mt-0.5 h-4 w-4 shrink-0 cursor-pointer rounded border-border-strong accent-brand",
          "transition-[border-color,background-color] duration-150",
          "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus",
        )}
        {...rest}
      />
      <div className="min-w-0">
        <label htmlFor={inputId} className="cursor-pointer text-sm text-text-primary">
          {label}
        </label>
        {hint && (
          <p id={describedBy} className="text-meta">
            {hint}
          </p>
        )}
      </div>
    </div>
  );
}

export interface RadioOption {
  value: string;
  label: ReactNode;
  hint?: string;
  disabled?: boolean;
}

export interface RadioGroupProps {
  legend: string;
  name: string;
  options: RadioOption[];
  value: string;
  onChange: (value: string) => void;
  orientation?: "vertical" | "horizontal";
  hint?: string;
  className?: string;
}

export function RadioGroup({
  legend,
  name,
  options,
  value,
  onChange,
  orientation = "vertical",
  hint,
  className,
}: RadioGroupProps) {
  const autoId = useId();
  const describedBy = hint ? `${autoId}-hint` : undefined;

  return (
    <fieldset className={cx("min-w-0", className)} aria-describedby={describedBy}>
      <legend className="text-label">{legend}</legend>
      <div
        className={cx(
          "mt-1.5",
          orientation === "vertical" ? "flex flex-col gap-1.5" : "flex flex-wrap items-center gap-x-4 gap-y-1.5",
        )}
      >
        {options.map((o) => (
          <label key={o.value} className={cx("flex items-start gap-2", o.disabled && "opacity-50")}>
            <input
              type="radio"
              name={name}
              value={o.value}
              checked={value === o.value}
              disabled={o.disabled}
              onChange={() => onChange(o.value)}
              className="mt-0.5 h-4 w-4 shrink-0 cursor-pointer border-border-strong accent-brand focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus"
            />
            <span className="min-w-0">
              <span className="block cursor-pointer text-sm text-text-primary">{o.label}</span>
              {o.hint && <span className="block text-meta">{o.hint}</span>}
            </span>
          </label>
        ))}
      </div>
      {hint && (
        <p id={describedBy} className="mt-1.5 text-meta">
          {hint}
        </p>
      )}
    </fieldset>
  );
}

export interface SwitchProps {
  label: ReactNode;
  checked: boolean;
  onChange: (checked: boolean) => void;
  hint?: string;
  /** Keeps the label off-screen (sidebar footer, dense toolbars). */
  hideLabel?: boolean;
  className?: string;
  disabled?: boolean;
  /** Explains the consequence of toggling - used where the state depends on
   *  the OS ("your system asks for reduced motion"). */
  title?: string;
}

/** Immediate, non-formal setting (motion on/off, density) - role=switch so
 *  assistive tech announces the on/off state, not a checked checkbox. */
export function Switch({ label, checked, onChange, hint, hideLabel, className, disabled, title }: SwitchProps) {
  const autoId = useId();
  const labelId = `${autoId}-label`;

  return (
    <div className={cx("min-w-0", className)}>
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        aria-labelledby={labelId}
        title={title}
        disabled={disabled}
        onClick={() => onChange(!checked)}
        className={cx(
          "flex w-full items-center justify-between gap-3 rounded-md px-1.5 py-1.5 text-sm text-text-secondary",
          "transition-colors duration-150 hover:bg-hovered hover:text-text-primary",
          "disabled:cursor-not-allowed disabled:opacity-50",
          hideLabel && "w-auto px-1",
        )}
      >
        <span id={labelId} className={cx("truncate", hideLabel && "sr-only")}>
          {label}
        </span>
        <span
          aria-hidden="true"
          className={cx(
            "relative h-[18px] w-8 shrink-0 rounded-full transition-colors duration-200 ease-[var(--ease-out-quart)]",
            checked ? "bg-brand" : "bg-border-strong",
          )}
        >
          <span
            className={cx(
              "absolute left-0.5 top-0.5 h-3.5 w-3.5 rounded-full bg-white shadow-sm transition-transform duration-200 ease-[var(--ease-out-expo)]",
              checked && "translate-x-[14px]",
            )}
          />
        </span>
      </button>
      {hint && <p className="px-1.5 text-meta">{hint}</p>}
    </div>
  );
}
