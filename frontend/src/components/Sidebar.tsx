import { useEffect, useLayoutEffect, useRef, useState, type ReactNode } from "react";
import gridPilotLogo from "../assets/gridpilot-logo.png";
import MotionToggle from "./MotionToggle";
import { IconSearch, IconUpload } from "./icons";
import { Tooltip } from "../ui/Tooltip";
import { cx } from "../ui/cx";
import type { IngestStatus } from "../types";

export type Tab =
  | "dashboard"
  | "timetable"
  | "blocking"
  | "teachers"
  | "teacher-loads"
  | "staffing-policy"
  | "rooms"
  | "findings"
  | "composites"
  | "room-constraints"
  | "teacher-capabilities"
  | "teaching-requirements"
  | "changes"
  | "audit";

export interface SidebarItem {
  id: Tab;
  label: string;
  icon: (className?: string) => ReactNode;
  /** Explains the item when the rail is collapsed and in tooltips. */
  description?: string;
}

export interface SidebarGroup {
  title: string;
  items: SidebarItem[];
}

interface Props {
  groups: SidebarGroup[];
  activeTab: Tab;
  onTabChange: (tab: Tab) => void;
  badgeFor: (tab: Tab) => number;
  ingestStatus: IngestStatus;
  onImportClick: () => void;
  onSearchClick: () => void;
}

const COLLAPSE_KEY = "gridpilot.sidebar";

function sourceFileName(path: string | null): string | null {
  if (!path) return null;
  const base = path.split(/[\\/]/).pop() ?? path;
  // Browser-uploaded files are staged on disk with a "<timestamp>_" prefix
  // for collision-safety (see app/api/ingest.py) - strip it back off for
  // display so it reads as the file the user actually chose.
  return base.replace(/^\d{8}T\d{12}_/, "");
}

function formatImportedAt(iso: string | null | undefined): string {
  if (!iso) return "Not yet imported";
  const d = new Date(iso);
  const today = new Date();
  const sameDay = d.toDateString() === today.toDateString();
  return sameDay
    ? `Imported today, ${d.toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" })}`
    : `Imported ${d.toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" })}`;
}

/** The application navigation. Two densities: an expanded rail with labels and
 *  a 56px icon rail, chosen by the user and forced to the icon rail on narrow
 *  windows so content never loses its width. Collapsed items keep their
 *  accessible name via a focus-reachable tooltip. */
export default function Sidebar({
  groups,
  activeTab,
  onTabChange,
  badgeFor,
  ingestStatus,
  onImportClick,
  onSearchClick,
}: Props) {
  const fileName = sourceFileName(ingestStatus.last_ingest?.tfx_source_path ?? null);
  const isMac = typeof navigator !== "undefined" && /mac/i.test(navigator.platform ?? "");

  const [storedCollapsed, setStoredCollapsed] = useState<boolean>(() => {
    try {
      return localStorage.getItem(COLLAPSE_KEY) === "collapsed";
    } catch {
      return false;
    }
  });
  // Below lg the window simply doesn't have room for a labelled rail; the
  // stored preference still applies once there is.
  const [isNarrow, setIsNarrow] = useState(
    () => typeof window !== "undefined" && !window.matchMedia("(min-width: 1024px)").matches,
  );
  useEffect(() => {
    const mq = window.matchMedia("(min-width: 1024px)");
    const onChange = () => setIsNarrow(!mq.matches);
    onChange();
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, []);

  const collapsed = isNarrow || storedCollapsed;
  const toggleCollapsed = () => {
    const next = !storedCollapsed;
    setStoredCollapsed(next);
    try {
      localStorage.setItem(COLLAPSE_KEY, next ? "collapsed" : "expanded");
    } catch {
      // Preference just won't persist - it still applies now.
    }
  };

  // The active-item highlight is one element that glides to wherever the
  // active tab is, rather than a background that snaps on/off per button -
  // so the eye follows where you moved to. Not animated on first paint.
  const itemRefs = useRef<Record<string, HTMLButtonElement | null>>({});
  const [indicator, setIndicator] = useState<{ top: number; height: number } | null>(null);
  const [indicatorReady, setIndicatorReady] = useState(false);
  useLayoutEffect(() => {
    const el = itemRefs.current[activeTab];
    if (!el) return;
    setIndicator({ top: el.offsetTop, height: el.offsetHeight });
    const frame = requestAnimationFrame(() => setIndicatorReady(true));
    return () => cancelAnimationFrame(frame);
  }, [activeTab, groups, collapsed]);

  const statusLine = formatImportedAt(ingestStatus.last_ingest?.finished_at ?? ingestStatus.last_ingest?.started_at);

  const searchButton = (
    <button
      type="button"
      onClick={onSearchClick}
      className={cx(
        "flex w-full items-center gap-2 border border-border bg-surface-sunken text-text-muted",
        "transition-colors duration-150 hover:border-border-strong hover:bg-surface hover:text-text-secondary",
        "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus",
        collapsed ? "h-8.5 w-8.5 justify-center rounded-md p-0" : "rounded-md px-2.5 py-1.5 text-sm",
      )}
    >
      <IconSearch className="h-4 w-4 shrink-0" />
      {collapsed ? (
        <span className="sr-only">Search (Ctrl {isMac ? "or Command" : ""} K)</span>
      ) : (
        <>
          <span className="flex-1 text-left">Search…</span>
          <kbd className="rounded border border-border-strong bg-surface px-1 py-0.5 text-[10px] font-medium text-text-muted">
            {isMac ? "⌘K" : "Ctrl K"}
          </kbd>
        </>
      )}
    </button>
  );

  const importButton = (
    <button
      type="button"
      onClick={onImportClick}
      className={cx(
        "flex items-center justify-center gap-1.5 border border-border-strong bg-surface text-text-secondary",
        "transition-colors duration-150 hover:bg-hovered hover:text-text-primary",
        "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus",
        collapsed ? "h-8.5 w-8.5 rounded-md p-0" : "w-full rounded-md px-3 py-1.5 text-sm font-medium",
      )}
    >
      <IconUpload className="h-4 w-4 shrink-0" />
      <span className={collapsed ? "sr-only" : undefined}>Import…</span>
    </button>
  );

  return (
    <aside
      className={cx(
        "flex h-dvh shrink-0 flex-col border-r border-border bg-surface print:hidden",
        "transition-[width] duration-200 ease-[var(--ease-out-quart)]",
        collapsed ? "w-14" : "w-60",
      )}
    >
      {/* Brand + collapse control */}
      <div className={cx("flex items-center gap-2 border-b border-border", collapsed ? "justify-center px-2 py-3" : "px-3 py-3")}>
        <img src={gridPilotLogo} alt="GridPilot" className="h-6 w-auto" />
        <button
          type="button"
          onClick={toggleCollapsed}
          aria-expanded={!collapsed}
          aria-label={collapsed ? "Expand navigation" : "Collapse navigation"}
          title={collapsed ? "Expand navigation" : "Collapse navigation"}
          className={cx(
            "flex h-7 w-7 shrink-0 items-center justify-center rounded-md text-text-muted",
            "transition-colors duration-150 hover:bg-hovered hover:text-text-primary",
            "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus",
            collapsed && "hidden",
          )}
        >
          <svg viewBox="0 0 16 16" className="h-4 w-4" fill="none" aria-hidden="true">
            <path d="M10 3.5 5.5 8 10 12.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </button>
      </div>

      <div className={cx("pt-3", collapsed ? "px-2" : "px-3")}>
        {collapsed ? (
          <Tooltip content="Search (Ctrl K)" placement="right">
            {searchButton}
          </Tooltip>
        ) : (
          searchButton
        )}
      </div>

      <nav
        aria-label="Primary"
        className="min-h-0 flex-1 overflow-y-auto overflow-x-hidden py-3"
        style={{ paddingLeft: collapsed ? 8 : 12, paddingRight: collapsed ? 8 : 12 }}
      >
        <div className="relative flex flex-col gap-3.5">
          {indicator && (
            <div
              aria-hidden="true"
              className={cx(
                "pointer-events-none absolute inset-x-0 top-0 rounded-md bg-selected",
                indicatorReady ? "transition-[transform,height] duration-300 ease-[var(--ease-out-expo)]" : "",
              )}
              style={{ transform: `translateY(${indicator.top}px)`, height: indicator.height }}
            >
              <span className="absolute inset-y-1.5 left-0 w-0.5 rounded-full bg-brand" />
            </div>
          )}
          {groups.map((group) => (
            <div key={group.title}>
              {collapsed ? (
                <div aria-hidden="true" className="mx-2 mb-2 border-t border-border" />
              ) : (
                <p className="mb-1 px-2.5 text-label">{group.title}</p>
              )}
              <div className="flex flex-col gap-0.5">
                {group.items.map((item) => {
                  const active = activeTab === item.id;
                  const count = badgeFor(item.id);
                  const button = (
                    <button
                      key={item.id}
                      ref={(el) => {
                        itemRefs.current[item.id] = el;
                      }}
                      type="button"
                      onClick={() => onTabChange(item.id)}
                      aria-current={active ? "page" : undefined}
                      className={cx(
                        "relative flex items-center gap-2.5 rounded-md text-sm font-medium",
                        "transition-colors duration-150",
                        "focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-focus",
                        collapsed ? "h-9 justify-center px-0" : "px-2.5 py-1.5",
                        active ? "text-brand" : "text-text-secondary hover:bg-hovered hover:text-text-primary",
                      )}
                    >
                      {item.icon(
                        cx(
                          "h-4.5 w-4.5 shrink-0 transition-colors duration-150",
                          active ? "text-brand" : "text-text-muted",
                        ),
                      )}
                      {collapsed ? (
                        <span className="sr-only">{item.label}</span>
                      ) : (
                        <span className="flex-1 truncate text-left">{item.label}</span>
                      )}
                      {count > 0 &&
                        (collapsed ? (
                          <span
                            aria-hidden="true"
                            className="absolute -right-1 -top-1 flex h-4 min-w-4 items-center justify-center rounded-full bg-brand px-1 text-[9px] font-semibold leading-none text-on-inverse nums shadow-sm"
                          >
                            {count > 99 ? "99+" : count}
                          </span>
                        ) : (
                          <span
                            className={cx(
                              "rounded-full px-1.5 py-0.5 text-xs font-semibold leading-none transition-colors duration-150 nums",
                              active ? "bg-brand text-on-inverse" : "bg-surface-sunken text-text-muted",
                            )}
                          >
                            {count}
                          </span>
                        ))}
                    </button>
                  );

                  if (!collapsed) return button;
                  const countSuffix = count > 0 ? `, ${count} waiting` : "";
                  return (
                    <Tooltip key={item.id} content={`${item.label}${countSuffix}`} placement="right">
                      {button}
                    </Tooltip>
                  );
                })}
              </div>
            </div>
          ))}
        </div>
      </nav>

      {/* Data source + settings. The "imported what / when" answer lives here
          permanently so the shell, not just the dashboard, always states what
          data is loaded. */}
      <div className={cx("border-t border-border", collapsed ? "px-2 py-2.5" : "px-3 py-3")}>
        <div className={cx("mb-2 flex items-start gap-2", collapsed && "justify-center")}>
          <span
            aria-hidden="true"
            className="mt-1 h-2 w-2 shrink-0 rounded-full bg-success"
            title={fileName ?? "No file loaded"}
          />
          <div className={cx("min-w-0 flex-1", collapsed && "hidden")}>
            <p className="truncate text-xs font-medium text-text-primary" title={fileName ?? undefined}>
              {fileName ?? "No file loaded"}
            </p>
            <p className="truncate text-meta" title={statusLine}>
              {statusLine}
            </p>
          </div>
        </div>

        <div className={collapsed ? "hidden" : undefined}>
          <MotionToggle />
        </div>

        {collapsed ? (
          <Tooltip content="Import a timetable" placement="right">
            {importButton}
          </Tooltip>
        ) : (
          importButton
        )}
      </div>
    </aside>
  );
}
