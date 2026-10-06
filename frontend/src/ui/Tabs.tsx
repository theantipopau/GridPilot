import { useRef, type KeyboardEvent } from "react";
import { cx } from "./cx";

export interface TabItem<T extends string = string> {
  id: T;
  label: string;
  /** Count shown after the label - review queues are count-first. */
  count?: number;
  disabled?: boolean;
}

interface TabsProps<T extends string> {
  tabs: TabItem<T>[];
  value: T;
  onChange: (id: T) => void;
  /** "underline" for page-level sections, "segmented" for inline mode switches. */
  variant?: "underline" | "segmented";
  size?: "sm" | "md";
  /** Connects the tablist to the panel it controls (aria-controls). */
  panelId?: string;
  label: string;
  className?: string;
}

/** Proper tablist: roving arrow-key navigation, Home/End, aria-selected and
 *  aria-controls. The six bespoke tab strips in the app were plain buttons
 *  with no arrow keys and no selected state exposed. */
export function Tabs<T extends string>({
  tabs,
  value,
  onChange,
  variant = "underline",
  size = "md",
  panelId,
  label,
  className,
}: TabsProps<T>) {
  const refs = useRef<Record<string, HTMLButtonElement | null>>({});

  const onKeyDown = (e: KeyboardEvent<HTMLDivElement>) => {
    const enabled = tabs.filter((t) => !t.disabled);
    const idx = enabled.findIndex((t) => t.id === value);
    if (idx < 0) return;
    let next: number | null = null;
    if (e.key === "ArrowRight" || e.key === "ArrowDown") next = (idx + 1) % enabled.length;
    else if (e.key === "ArrowLeft" || e.key === "ArrowUp") next = (idx - 1 + enabled.length) % enabled.length;
    else if (e.key === "Home") next = 0;
    else if (e.key === "End") next = enabled.length - 1;
    if (next == null) return;
    e.preventDefault();
    const target = enabled[next];
    onChange(target.id);
    refs.current[target.id]?.focus();
  };

  if (variant === "segmented") {
    return (
      <div
        role="tablist"
        aria-label={label}
        onKeyDown={onKeyDown}
        className={cx("inline-flex items-center gap-0.5 rounded-md bg-surface-sunken p-1", className)}
      >
        {tabs.map((t) => {
          const active = t.id === value;
          return (
            <button
              key={t.id}
              ref={(el) => {
                refs.current[t.id] = el;
              }}
              type="button"
              role="tab"
              id={panelId ? `${panelId}-tab-${t.id}` : undefined}
              aria-controls={panelId}
              aria-selected={active}
              disabled={t.disabled}
              tabIndex={active ? 0 : -1}
              onClick={() => onChange(t.id)}
              className={cx(
                "rounded px-3 font-medium transition-colors duration-150 ease-[var(--ease-out-quart)]",
                size === "sm" ? "py-1.5 text-xs" : "py-1.5 text-sm",
                "disabled:cursor-not-allowed disabled:opacity-50",
                active
                  ? "bg-surface text-text-primary shadow-sm"
                  : "text-text-muted hover:text-text-secondary",
              )}
            >
              {t.label}
              {t.count != null && <span className="nums ml-1.5 text-text-muted">{t.count}</span>}
            </button>
          );
        })}
      </div>
    );
  }

  return (
    <div
      role="tablist"
      aria-label={label}
      onKeyDown={onKeyDown}
      className={cx("flex gap-1 overflow-x-auto border-b border-border", className)}
    >
      {tabs.map((t) => {
        const active = t.id === value;
        return (
          <button
            key={t.id}
            ref={(el) => {
              refs.current[t.id] = el;
            }}
            type="button"
            role="tab"
            id={panelId ? `${panelId}-tab-${t.id}` : undefined}
            aria-controls={panelId}
            aria-selected={active}
            disabled={t.disabled}
            tabIndex={active ? 0 : -1}
            onClick={() => onChange(t.id)}
            className={cx(
              "relative whitespace-nowrap px-3 font-medium transition-colors duration-150",
              size === "sm" ? "py-2 text-xs" : "py-2.5 text-sm",
              "disabled:cursor-not-allowed disabled:opacity-50",
              active ? "text-brand" : "text-text-muted hover:text-text-secondary",
            )}
          >
            {t.label}
            {t.count != null && (
              <span
                className={cx(
                  "nums ml-1.5 rounded-full px-1.5 py-px text-[11px]",
                  active ? "bg-brand-surface text-brand" : "bg-surface-sunken text-text-muted",
                )}
              >
                {t.count}
              </span>
            )}
            <span
              aria-hidden="true"
              className={cx(
                "absolute inset-x-0 -bottom-px h-0.5 rounded-full transition-colors duration-150",
                active ? "bg-brand" : "bg-transparent",
              )}
            />
          </button>
        );
      })}
    </div>
  );
}

export interface BreadcrumbItem {
  label: string;
  onClick?: () => void;
}

/** Breadcrumbs only where they describe real location depth (page > section).
 *  Rendered by the shell, not by individual pages. */
export function Breadcrumb({ items, className }: { items: BreadcrumbItem[]; className?: string }) {
  if (items.length === 0) return null;
  return (
    <nav aria-label="Breadcrumb" className={cx("min-w-0", className)}>
      <ol className="flex items-center gap-1.5 overflow-hidden text-meta">
        {items.map((item, i) => {
          const last = i === items.length - 1;
          return (
            <li key={`${item.label}-${i}`} className="flex min-w-0 items-center gap-1.5">
              {i > 0 && (
                <span aria-hidden="true" className="text-text-muted shrink-0">
                  /
                </span>
              )}
              {last || !item.onClick ? (
                <span aria-current={last ? "page" : undefined} className="truncate text-text-secondary font-medium">
                  {item.label}
                </span>
              ) : (
                <button
                  type="button"
                  onClick={item.onClick}
                  className="truncate rounded px-0.5 text-text-muted transition-colors duration-150 hover:text-brand"
                >
                  {item.label}
                </button>
              )}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
