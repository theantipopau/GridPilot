import { useEffect, useMemo, useRef, useState } from "react";
import type { Tab } from "./Sidebar";
import { IconSearch } from "./icons";
import type { ReferenceData, ViewType } from "../types";

interface Result {
  key: string;
  kind: "Page" | "Teacher" | "Room" | "Roll class";
  label: string;
  sublabel?: string;
  onSelect: () => void;
}

interface Props {
  reference: ReferenceData;
  onClose: () => void;
  onNavigateTab: (tab: Tab) => void;
  onJumpToEntity: (view: ViewType, code: string) => void;
}

const PAGES: { label: string; tab: Tab }[] = [
  { label: "Dashboard", tab: "dashboard" },
  { label: "Timetable", tab: "timetable" },
  { label: "Blocking", tab: "blocking" },
  { label: "Teachers", tab: "teachers" },
  { label: "Staffing Policy", tab: "staffing-policy" },
  { label: "Rooms", tab: "rooms" },
  { label: "Findings", tab: "findings" },
  { label: "Composite Review", tab: "composites" },
  { label: "Room Constraints", tab: "room-constraints" },
  { label: "Teacher Capabilities", tab: "teacher-capabilities" },
  { label: "Change Sets", tab: "changes" },
  { label: "Audit", tab: "audit" },
];

export default function CommandPalette({ reference, onClose, onNavigateTab, onJumpToEntity }: Props) {
  const [query, setQuery] = useState("");
  const [highlighted, setHighlighted] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  const results = useMemo<Result[]>(() => {
    const q = query.trim().toLowerCase();
    const all: Result[] = [];

    for (const p of PAGES) {
      if (!q || p.label.toLowerCase().includes(q)) {
        all.push({ key: `page:${p.tab}`, kind: "Page", label: p.label, onSelect: () => onNavigateTab(p.tab) });
      }
    }
    if (!q) return all.slice(0, 8);

    for (const t of reference.teachers) {
      const name = `${t.first_name ?? ""} ${t.last_name ?? ""}`.trim();
      if (t.code.toLowerCase().includes(q) || name.toLowerCase().includes(q)) {
        all.push({
          key: `teacher:${t.code}`,
          kind: "Teacher",
          label: name || t.code,
          sublabel: t.code,
          onSelect: () => onJumpToEntity("teacher", t.code),
        });
      }
    }
    for (const r of reference.rooms) {
      if (r.code.toLowerCase().includes(q) || r.name.toLowerCase().includes(q)) {
        all.push({
          key: `room:${r.code}`,
          kind: "Room",
          label: r.name,
          sublabel: r.code,
          onSelect: () => onJumpToEntity("room", r.code),
        });
      }
    }
    for (const rc of reference.roll_classes) {
      if (rc.code.toLowerCase().includes(q)) {
        all.push({
          key: `roll_class:${rc.code}`,
          kind: "Roll class",
          label: rc.code,
          sublabel: rc.year_level_code ? `Year ${rc.year_level_code}` : undefined,
          onSelect: () => onJumpToEntity("roll_class", rc.code),
        });
      }
    }
    return all.slice(0, 20);
  }, [query, reference, onNavigateTab, onJumpToEntity]);

  useEffect(() => setHighlighted(0), [query]);

  const choose = (r: Result | undefined) => {
    if (!r) return;
    r.onSelect();
    onClose();
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center bg-slate-900/30 pt-[12vh]"
      onClick={onClose}
    >
      <div
        className="w-full max-w-lg overflow-hidden rounded-lg border border-slate-200 bg-white shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center gap-2 border-b border-slate-100 px-4 py-3">
          <IconSearch className="h-4 w-4 shrink-0 text-slate-400" />
          <input
            ref={inputRef}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Escape") onClose();
              else if (e.key === "ArrowDown") {
                e.preventDefault();
                setHighlighted((h) => Math.min(h + 1, results.length - 1));
              } else if (e.key === "ArrowUp") {
                e.preventDefault();
                setHighlighted((h) => Math.max(h - 1, 0));
              } else if (e.key === "Enter") {
                e.preventDefault();
                choose(results[highlighted]);
              }
            }}
            placeholder="Jump to a teacher, room, roll class, or page…"
            className="w-full text-sm text-slate-900 outline-none placeholder:text-slate-400"
          />
        </div>
        <div className="max-h-80 overflow-y-auto py-1">
          {results.length === 0 && (
            <p className="px-4 py-6 text-center text-sm text-slate-400">No matches</p>
          )}
          {results.map((r, i) => (
            <button
              key={r.key}
              type="button"
              onClick={() => choose(r)}
              onMouseEnter={() => setHighlighted(i)}
              className={`flex w-full items-center justify-between gap-3 px-4 py-2 text-left text-sm transition-colors duration-100 ${
                i === highlighted ? "bg-sky-50 text-sky-700" : "text-slate-700"
              }`}
            >
              <span className="flex items-baseline gap-2 truncate">
                <span className="truncate font-medium">{r.label}</span>
                {r.sublabel && <span className="shrink-0 text-xs text-slate-400">{r.sublabel}</span>}
              </span>
              <span className="shrink-0 rounded bg-slate-100 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-slate-400">
                {r.kind}
              </span>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
