import { useEffect, useId, useRef, useState, type ReactNode } from "react";
import { cx } from "./cx";

export type TooltipPlacement = "top" | "bottom" | "left" | "right";

interface TooltipProps {
  content: ReactNode;
  children: ReactNode;
  placement?: TooltipPlacement;
  /** Delay before showing on hover (immediate for keyboard focus). */
  delayMs?: number;
  className?: string;
}

const PLACEMENT_CLASS: Record<TooltipPlacement, string> = {
  top: "bottom-full left-1/2 -translate-x-1/2 mb-2",
  bottom: "top-full left-1/2 -translate-x-1/2 mt-2",
  left: "right-full top-1/2 -translate-y-1/2 mr-2",
  right: "left-full top-1/2 -translate-y-1/2 ml-2",
};

/** Accessible tooltip: opens on hover AND keyboard focus, is wired to the
 *  trigger with aria-describedby, and closes on Escape/blur/leave. Replaces
 *  the native title attributes the audit found carrying load-bearing grid
 *  information invisibly to keyboard users. */
export function Tooltip({ content, children, placement = "top", delayMs = 250, className }: TooltipProps) {
  const id = useId();
  const [open, setOpen] = useState(false);
  const timer = useRef<number | null>(null);

  const clear = () => {
    if (timer.current != null) window.clearTimeout(timer.current);
    timer.current = null;
  };

  useEffect(() => clear, []);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open]);

  const show = (immediate = false) => {
    clear();
    if (immediate || delayMs === 0) setOpen(true);
    else timer.current = window.setTimeout(() => setOpen(true), delayMs);
  };
  const hide = () => {
    clear();
    setOpen(false);
  };

  return (
    <span
      className={cx("relative inline-flex", className)}
      onPointerEnter={() => show()}
      onPointerLeave={hide}
      onFocusCapture={() => show(true)}
      onBlurCapture={hide}
      onKeyDown={(e) => {
        if (e.key === "Escape") hide();
      }}
    >
      <span aria-describedby={open ? id : undefined} className="inline-flex">
        {children}
      </span>
      {open && (
        <span
          id={id}
          role="tooltip"
          className={cx(
            "pointer-events-none absolute z-50 w-max max-w-64 rounded-md bg-inverse px-2 py-1 text-[11px] leading-4 text-on-inverse shadow-lg animate-fade-in",
            PLACEMENT_CLASS[placement],
          )}
        >
          {content}
        </span>
      )}
    </span>
  );
}

interface PopoverProps {
  /** Rendered as the clickable trigger; receives the ARIA wiring. */
  trigger: (props: { open: boolean; toggle: () => void; id: string }) => ReactNode;
  children: ReactNode | ((close: () => void) => ReactNode);
  open?: boolean;
  onOpenChange?: (open: boolean) => void;
  align?: "start" | "end";
  label?: string;
  className?: string;
}

/** Lightweight anchored panel for contextual actions and notes. Closes on
 *  outside pointer, Escape (returning focus to the trigger) and explicit
 *  close - the same contract the Dialog keeps. */
export function Popover({ trigger, children, open: controlledOpen, onOpenChange, align = "end", label, className }: PopoverProps) {
  const id = useId();
  const [uncontrolled, setUncontrolled] = useState(false);
  const open = controlledOpen ?? uncontrolled;
  const rootRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLElement>(null);

  const setOpen = (next: boolean) => {
    if (controlledOpen === undefined) setUncontrolled(next);
    onOpenChange?.(next);
    if (!next) triggerRef.current?.focus();
  };

  useEffect(() => {
    if (!open) return;
    const onPointerDown = (e: PointerEvent) => {
      if (!rootRef.current?.contains(e.target as Node)) {
        if (controlledOpen === undefined) setUncontrolled(false);
        onOpenChange?.(false);
      }
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    document.addEventListener("pointerdown", onPointerDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("pointerdown", onPointerDown);
      document.removeEventListener("keydown", onKey);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, controlledOpen]);

  return (
    <div ref={rootRef} className={cx("relative inline-block", className)}>
      <span
        ref={(el) => {
          triggerRef.current = el;
        }}
      >
        {trigger({ open, toggle: () => setOpen(!open), id })}
      </span>
      {open && (
        <div
          id={id}
          role="dialog"
          aria-label={label}
          className={cx(
            "absolute z-50 mt-1 min-w-56 rounded-lg border border-border bg-surface-elevated p-3 shadow-xl animate-panel-in",
            align === "end" ? "right-0" : "left-0",
          )}
        >
          {typeof children === "function" ? children(() => setOpen(false)) : children}
        </div>
      )}
    </div>
  );
}
