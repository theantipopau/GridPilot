import { useLayoutEffect, useRef, useState, type ReactNode } from "react";
import gridPilotLogo from "../assets/gridpilot-logo.png";
import MotionToggle from "./MotionToggle";
import { IconSearch, IconUpload } from "./icons";
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

function sourceFileName(path: string | null): string | null {
  if (!path) return null;
  const base = path.split(/[\\/]/).pop() ?? path;
  // Browser-uploaded files are staged on disk with a "<timestamp>_" prefix
  // for collision-safety (see app/api/ingest.py) - strip it back off for
  // display so it reads as the file the user actually chose.
  return base.replace(/^\d{8}T\d{12}_/, "");
}

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

  // The active-item highlight is one element that glides to wherever the
  // active tab is, rather than a background that snaps on/off per button -
  // so the eye follows where you moved to. It is not animated on first
  // paint (it would sweep in from the top on load).
  const itemRefs = useRef<Record<string, HTMLButtonElement | null>>({});
  const [indicator, setIndicator] = useState<{ top: number; height: number } | null>(null);
  const [indicatorReady, setIndicatorReady] = useState(false);
  useLayoutEffect(() => {
    const el = itemRefs.current[activeTab];
    if (!el) return;
    setIndicator({ top: el.offsetTop, height: el.offsetHeight });
    const frame = requestAnimationFrame(() => setIndicatorReady(true));
    return () => cancelAnimationFrame(frame);
  }, [activeTab, groups]);

  return (
    <aside className="flex h-screen w-60 shrink-0 flex-col border-r border-slate-200 bg-white print:hidden">
      <div className="flex items-center gap-2 border-b border-slate-100 px-4 py-4">
        <img src={gridPilotLogo} alt="GridPilot" className="h-7 w-auto" />
      </div>

      <div className="px-3 pt-3">
        <button
          type="button"
          onClick={onSearchClick}
          className="flex w-full items-center gap-2 rounded-md border border-slate-200 bg-slate-50 px-3 py-1.5 text-sm text-slate-500 transition-colors duration-150 hover:border-slate-300 hover:bg-white"
        >
          <IconSearch className="h-4 w-4 shrink-0 text-ink-muted" />
          <span className="flex-1 text-left">Search…</span>
          <kbd className="rounded border border-slate-300 bg-white px-1 py-0.5 text-[10px] font-medium text-ink-muted">
            {isMac ? "⌘K" : "Ctrl K"}
          </kbd>
        </button>
      </div>

      <nav className="flex-1 overflow-y-auto p-3">
        <div className="relative flex flex-col gap-4">
          {indicator && (
            <div
              aria-hidden="true"
              className={`pointer-events-none absolute inset-x-0 top-0 rounded-md bg-sky-50 ${
                indicatorReady
                  ? "transition-[transform,height] duration-300 ease-[var(--ease-out-expo)]"
                  : ""
              }`}
              style={{ transform: `translateY(${indicator.top}px)`, height: indicator.height }}
            >
              <span className="absolute inset-y-1.5 left-0 w-[3px] rounded-full bg-sky-600" />
            </div>
          )}
          {groups.map((group) => (
            <div key={group.title}>
              <p className="mb-1 px-3 text-[11px] font-semibold uppercase tracking-wider text-ink-muted">
                {group.title}
              </p>
              <div className="flex flex-col gap-1">
                {group.items.map((item) => {
                  const active = activeTab === item.id;
                  const count = badgeFor(item.id);
                  return (
                    <button
                      key={item.id}
                      ref={(el) => {
                        itemRefs.current[item.id] = el;
                      }}
                      type="button"
                      onClick={() => onTabChange(item.id)}
                      aria-current={active ? "page" : undefined}
                      className={`relative flex items-center gap-2.5 rounded-md px-3 py-2 text-sm font-medium transition-colors duration-200 ${
                        active ? "text-sky-700" : "text-slate-600 hover:bg-slate-50 hover:text-slate-900"
                      }`}
                    >
                      {item.icon(
                        `h-4 w-4 shrink-0 transition-colors duration-200 ${active ? "text-sky-600" : "text-ink-muted"}`,
                      )}
                      <span className="flex-1 text-left">{item.label}</span>
                      {count > 0 && (
                        <span
                          key={count}
                          className={`animate-pop rounded-full px-1.5 py-0.5 text-xs font-semibold tabular-nums transition-colors duration-200 ${
                            active ? "bg-sky-600 text-white" : "bg-slate-200 text-slate-600"
                          }`}
                        >
                          {count}
                        </span>
                      )}
                    </button>
                  );
                })}
              </div>
            </div>
          ))}
        </div>
      </nav>

      <div className="border-t border-slate-100 p-3">
        <p className="truncate text-xs font-medium text-slate-600" title={fileName ?? undefined}>
          {fileName ?? "No file loaded"}
        </p>
        <p className="mb-2 text-xs text-ink-muted">
          {ingestStatus.last_ingest?.finished_at
            ? `Imported ${new Date(ingestStatus.last_ingest.finished_at).toLocaleString()}`
            : "Sophia College"}
        </p>
        <MotionToggle />
        <button
          type="button"
          onClick={onImportClick}
          className="flex w-full items-center justify-center gap-1.5 rounded-md border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-700 transition-colors duration-150 hover:border-slate-400 hover:bg-slate-50"
        >
          <IconUpload className="h-4 w-4" />
          Import…
        </button>
      </div>
    </aside>
  );
}
