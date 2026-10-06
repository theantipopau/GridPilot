import { useEffect, useId, useMemo, useRef, useState, type KeyboardEvent } from "react";
import { cx } from "./cx";
import { FieldShell, type FieldSize } from "./Input";

export interface SelectOption {
  value: string;
  label: string;
  disabled?: boolean;
}

interface SelectBase {
  label?: string;
  hint?: string;
  error?: string;
  size?: FieldSize;
  className?: string;
  containerClassName?: string;
  required?: boolean;
}

export interface SelectProps extends SelectBase {
  options: SelectOption[];
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  id?: string;
  disabled?: boolean;
}

const NATIVE_CLASS =
  "w-full appearance-none rounded-md border bg-surface text-sm text-text-primary " +
  "transition-[border-color,box-shadow] duration-150 ease-[var(--ease-out-quart)] " +
  "disabled:cursor-not-allowed disabled:bg-surface-sunken disabled:text-text-muted";

const NATIVE_SIZE: Record<FieldSize, string> = {
  sm: "h-7 pl-2 pr-7 text-xs",
  md: "h-8.5 pl-2.5 pr-8 text-sm",
};

function tone(error?: string): string {
  return error
    ? "border-critical focus:border-critical"
    : "border-border-strong hover:border-border-strong/90";
}

/** Native <select> - keyboard, mobile and screen-reader behaviour for free.
 *  Use this unless the list needs search; then use Combobox. */
export function Select({
  options,
  value,
  onChange,
  label,
  hint,
  error,
  size = "md",
  className,
  containerClassName,
  placeholder,
  id,
  disabled,
  required,
}: SelectProps) {
  const autoId = useId();
  const selectId = id ?? autoId;
  const describedBy = error ? `${selectId}-error` : hint ? `${selectId}-hint` : undefined;

  return (
    <FieldShell id={selectId} label={label} hint={hint} error={error} required={required} className={containerClassName}>
      <div className="relative">
        <select
          id={selectId}
          value={value}
          disabled={disabled}
          required={required}
          aria-invalid={error ? true : undefined}
          aria-describedby={describedBy}
          onChange={(e) => onChange(e.target.value)}
          className={cx(
            NATIVE_CLASS,
            NATIVE_SIZE[size],
            tone(error),
            "focus:border-focus focus:outline-none focus:shadow-[0_0_0_3px_color-mix(in_oklab,var(--color-focus)_22%,transparent)]",
            className,
          )}
        >
          {placeholder && (
            <option value="" disabled>
              {placeholder}
            </option>
          )}
          {options.map((o) => (
            <option key={o.value} value={o.value} disabled={o.disabled}>
              {o.label}
            </option>
          ))}
        </select>
        <svg
          viewBox="0 0 16 16"
          aria-hidden="true"
          className={cx(
            "pointer-events-none absolute top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-text-muted",
            size === "sm" ? "right-2" : "right-2.5",
          )}
          fill="none"
        >
          <path d="m4 6 4 4 4-4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </div>
    </FieldShell>
  );
}

export interface ComboboxProps extends SelectBase {
  options: SelectOption[];
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  id?: string;
  emptyText?: string;
  disabled?: boolean;
}

/** Filterable single-select (WAI-ARIA combobox with a listbox popup).
 *  Needed where the option list is long enough that a native select is a
 *  scroll marathon - teachers (~75) and rooms (~51). */
export function Combobox({
  options,
  value,
  onChange,
  label,
  hint,
  error,
  size = "md",
  className,
  containerClassName,
  placeholder,
  id,
  emptyText = "No matches",
  disabled,
  required,
}: ComboboxProps) {
  const autoId = useId();
  const rootId = id ?? autoId;
  const listId = `${rootId}-list`;
  const inputId = `${rootId}-input`;
  const describedBy = error ? `${rootId}-error` : hint ? `${rootId}-hint` : undefined;

  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(0);
  const rootRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLUListElement>(null);

  const selectedLabel = options.find((o) => o.value === value)?.label ?? "";
  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return options;
    return options.filter((o) => o.label.toLowerCase().includes(q) || o.value.toLowerCase().includes(q));
  }, [options, query]);

  // Close on outside click / Escape without tearing down the caller's state.
  useEffect(() => {
    if (!open) return;
    const onPointerDown = (e: PointerEvent) => {
      if (!rootRef.current?.contains(e.target as Node)) {
        setOpen(false);
        setQuery("");
      }
    };
    document.addEventListener("pointerdown", onPointerDown);
    return () => document.removeEventListener("pointerdown", onPointerDown);
  }, [open]);

  useEffect(() => {
    if (open) setActive(Math.max(0, filtered.findIndex((o) => o.value === value)));
  }, [open, filtered, value]);

  useEffect(() => {
    if (!open) return;
    listRef.current?.querySelector<HTMLElement>(`[data-index="${active}"]`)?.scrollIntoView({ block: "nearest" });
  }, [active, open]);

  const commit = (option: SelectOption | undefined) => {
    if (!option || option.disabled) return;
    onChange(option.value);
    setOpen(false);
    setQuery("");
    inputRef.current?.focus();
  };

  const onKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      e.preventDefault();
      if (!open) {
        setOpen(true);
        return;
      }
      const dir = e.key === "ArrowDown" ? 1 : -1;
      setActive((i) => {
        const next = i + dir;
        if (next < 0) return filtered.length - 1;
        if (next >= filtered.length) return 0;
        return next;
      });
    } else if (e.key === "Enter") {
      if (open) {
        e.preventDefault();
        commit(filtered[active]);
      }
    } else if (e.key === "Escape") {
      if (open) {
        e.preventDefault();
        setOpen(false);
        setQuery("");
      }
    } else if (e.key === "Tab") {
      setOpen(false);
      setQuery("");
    }
  };

  return (
    <FieldShell id={inputId} label={label} hint={hint} error={error} required={required} className={containerClassName}>
      <div ref={rootRef} className="relative">
        <input
          ref={inputRef}
          id={inputId}
          role="combobox"
          type="text"
          autoComplete="off"
          disabled={disabled}
          required={required}
          aria-expanded={open}
          aria-controls={listId}
          aria-autocomplete="list"
          aria-activedescendant={open && filtered[active] ? `${listId}-${active}` : undefined}
          aria-invalid={error ? true : undefined}
          aria-describedby={describedBy}
          value={open ? query : selectedLabel}
          placeholder={placeholder}
          onFocus={() => setOpen(true)}
          onChange={(e) => {
            setQuery(e.target.value);
            setActive(0);
            if (!open) setOpen(true);
          }}
          onKeyDown={onKeyDown}
          className={cx(
            NATIVE_CLASS,
            NATIVE_SIZE[size],
            "pr-8",
            tone(error),
            "focus:border-focus focus:outline-none focus:shadow-[0_0_0_3px_color-mix(in_oklab,var(--color-focus)_22%,transparent)]",
            className,
          )}
        />
        <svg
          viewBox="0 0 16 16"
          aria-hidden="true"
          className={cx(
            "pointer-events-none absolute top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-text-muted",
            size === "sm" ? "right-2" : "right-2.5",
          )}
          fill="none"
        >
          <path d="m4 6 4 4 4-4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
        </svg>

        {open && (
          <ul
            ref={listRef}
            id={listId}
            role="listbox"
            aria-label={label ?? placeholder ?? "Options"}
            className="absolute z-40 mt-1 max-h-64 w-full min-w-56 overflow-y-auto rounded-md border border-border bg-surface-elevated p-1 shadow-lg animate-fade-in"
          >
            {filtered.length === 0 && <li className="px-2 py-2 text-meta">{emptyText}</li>}
            {filtered.map((o, i) => (
              <li
                key={o.value}
                id={`${listId}-${i}`}
                data-index={i}
                role="option"
                aria-selected={o.value === value}
                aria-disabled={o.disabled}
                onPointerDown={(e) => {
                  e.preventDefault();
                  commit(o);
                }}
                onPointerEnter={() => setActive(i)}
                className={cx(
                  "cursor-pointer truncate rounded px-2 py-1.5 text-sm",
                  i === active ? "bg-selected text-text-primary" : "text-text-secondary",
                  o.value === value && "font-medium text-brand",
                  o.disabled && "cursor-not-allowed opacity-50",
                )}
              >
                {o.label}
              </li>
            ))}
          </ul>
        )}
      </div>
    </FieldShell>
  );
}
