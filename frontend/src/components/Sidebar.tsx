import type { ReactNode } from "react";
import gridPilotLogo from "../assets/gridpilot-logo.png";
import { IconSearch, IconUpload } from "./icons";
import type { IngestStatus } from "../types";

export type Tab =
  | "dashboard"
  | "timetable"
  | "blocking"
  | "teachers"
  | "staffing-policy"
  | "rooms"
  | "findings"
  | "composites"
  | "room-constraints"
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

  return (
    <aside className="flex h-screen w-60 shrink-0 flex-col border-r border-slate-200 bg-white">
      <div className="flex items-center gap-2 border-b border-slate-100 px-4 py-4">
        <img src={gridPilotLogo} alt="GridPilot" className="h-7 w-auto" />
      </div>

      <div className="px-3 pt-3">
        <button
          type="button"
          onClick={onSearchClick}
          className="flex w-full items-center gap-2 rounded-md border border-slate-200 bg-slate-50 px-3 py-1.5 text-sm text-slate-500 transition-colors duration-150 hover:border-slate-300 hover:bg-white"
        >
          <IconSearch className="h-4 w-4 shrink-0 text-slate-400" />
          <span className="flex-1 text-left">Search…</span>
          <kbd className="rounded border border-slate-300 bg-white px-1 py-0.5 text-[10px] font-medium text-slate-400">
            {isMac ? "⌘K" : "Ctrl K"}
          </kbd>
        </button>
      </div>

      <nav className="flex flex-1 flex-col gap-4 overflow-y-auto p-3">
        {groups.map((group) => (
          <div key={group.title}>
            <p className="mb-1 px-3 text-[11px] font-semibold uppercase tracking-wider text-slate-400">
              {group.title}
            </p>
            <div className="flex flex-col gap-1">
              {group.items.map((item) => {
                const active = activeTab === item.id;
                const count = badgeFor(item.id);
                return (
                  <button
                    key={item.id}
                    type="button"
                    onClick={() => onTabChange(item.id)}
                    className={`flex items-center gap-2.5 rounded-md px-3 py-2 text-sm font-medium transition-colors duration-150 ${
                      active ? "bg-sky-50 text-sky-700" : "text-slate-600 hover:bg-slate-50 hover:text-slate-900"
                    }`}
                  >
                    {item.icon(active ? "h-4 w-4 shrink-0 text-sky-600" : "h-4 w-4 shrink-0 text-slate-400")}
                    <span className="flex-1 text-left">{item.label}</span>
                    {count > 0 && (
                      <span
                        className={`rounded-full px-1.5 py-0.5 text-xs font-semibold transition-colors duration-150 ${
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
      </nav>

      <div className="border-t border-slate-100 p-3">
        <p className="truncate text-xs font-medium text-slate-600" title={fileName ?? undefined}>
          {fileName ?? "No file loaded"}
        </p>
        <p className="mb-3 text-xs text-slate-400">
          {ingestStatus.last_ingest?.finished_at
            ? `Imported ${new Date(ingestStatus.last_ingest.finished_at).toLocaleString()}`
            : "Sophia College"}
        </p>
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
