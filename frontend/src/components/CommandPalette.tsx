import { useEffect, useMemo, useRef, useState, type KeyboardEvent } from "react";
import type { Tab } from "./Sidebar";
import { IconSearch } from "./icons";
import { useFocusTrap } from "../ui/useFocusTrap";
import { cx } from "../ui/cx";
import type { ReferenceData, ViewType } from "../types";

interface Result {
  key: string;
  kind: "Page" | "Teacher" | "Room" | "Roll class";
  group: string;
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

/** Pages in navigation order, so the palette reinforces the same workflow the
 *  sidebar teaches (docs/ui-ux-audit.md §3.1). */
const PAGES: { label: string; tab: Tab; group: string }[] = [
  { label: "Dashboard", tab: "dashboard", group: "Overview" },
  { label: "Master grid", tab: "timetable", group: "Review timetable" },
  { label: "Teachers", tab: "teachers", group: "Review timetable" },
  { label: "Teacher loads", tab: "teacher-loads", group: "Review timetable" },
  { label: "Rooms", tab: "rooms", group: "Review timetable" },
  { label: "Findings", tab: "findings", group: "Investigate findings" },
  { label: "Composite review", tab: "composites", group: "Investigate findings" },
  { label: "Room constraints", tab: "room-constraints", group: "Investigate findings" },
  { label: "Teacher capabilities", tab: "teacher-capabilities", group: "Investigate findings" },
  { label: "Teaching requirements", tab: "teaching-requirements", group: "Investigate findings" },
  { label: "Change sets", tab: "changes", group: "Test & approve changes" },
  { label: "Audit", tab: "audit", group: "Export & audit" },
  { label: "Blocking", tab: "blocking", group: "Specialist" },
  { label: "Staffing policy", tab: "staffing-policy", group: "Specialist" },
];

/** Jump-to navigation: pages first, then matching entities. Focus is moved
 *  into the dialog on open and returned to the trigger on close (the shared
 *  focus contract), Escape closes from anywhere including the list. */
export default function CommandPalette({ reference, onClose, onNavigateTab, onJumpToEntity }: Props) {
  const [query, setQuery] = useState("");
  const [highlighted, setHighlighted] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const trapRef = useFocusTrap(true, onClose);

  const results = useMemo<Result[]>(() => {
    const q = query.trim().toLowerCase();
    const all: Result[] = [];

    for (const p of PAGES) {
      if (!q || p.label.toLowerCase().includes(q)) {
        all.push({
          key: `page:${p.tab}`,
          kind: "Page",
          group: p.group,
          label: p.label,
          onSelect: () => onNavigateTab(p.tab),
        });
      }
    }
    if (!q) return all.slice(0, 8);

    for (const t of reference.teachers) {
      const name = `${t.first_name ?? ""} ${t.last_name ?? ""}`.trim();
      if (t.code.toLowerCase().includes(q) || name.toLowerCase().includes(q)) {
        all.push({
          key: `teacher:${t.code}`,
          kind: "Teacher",
          group: "Jump to",
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
          group: "Jump to",
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
          group: "Jump to",
          label: rc.code,
          sublabel: rc.year_level_code ? `Year ${rc.year_level_code}` : undefined,
          onSelect: () => onJumpToEntity("roll_class", rc.code),
        });
      }
    }
    return all.slice(0, 24);
  }, [query, reference, onNavigateTab, onJumpToEntity]);

  useEffect(() => setHighlighted(0), [query]);

  const choose = (r: Result | undefined) => {
    if (!r) return;
    r.onSelect();
    onClose();
  };

  const onKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setHighlighted((h) => Math.min(h + 1, results.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setHighlighted((h) => Math.max(h - 1, 0));
    } else if (e.key === "Enter") {
      e.preventDefault();
      choose(results[highlighted]);
    }
  };

  // Group headers are derived, not hand-maintained: whatever order results
  // come back in, the header is emitted when the group changes.
  let lastGroup: string | null = null;

  return (
    <div
      className="fixed inset-0 z-50 flex animate-fade-in items-start justify-center bg-scrim pt-[12vh] backdrop-blur-[2px]"
      onPointerDown={onClose}
    >
      <div
        ref={trapRef}
        role="dialog"
        aria-modal="true"
        aria-label="Command palette"
        tabIndex={-1}
        className="w-full max-w-lg animate-panel-in overflow-hidden rounded-xl border border-border bg-surface-elevated shadow-2xl"
        onPointerDown={(e) => e.stopPropagation()}
      >
        <div className="flex items-center gap-2 border-b border-border px-4 py-3">
          <IconSearch className="h-4 w-4 shrink-0 text-text-muted" />
          <input
            ref={inputRef}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={onKeyDown}
            role="combobox"
            aria-expanded="true"
            aria-controls="command-palette-results"
            aria-activedescendant={results[highlighted] ? `command-result-${highlighted}` : undefined}
            aria-autocomplete="list"
            aria-label="Jump to a teacher, room, roll class, or page"
            placeholder="Jump to a teacher, room, roll class, or page…"
            className="w-full bg-transparent text-sm text-text-primary outline-none placeholder:text-text-muted"
          />
          <kbd className="shrink-0 rounded border border-border-strong bg-surface-sunken px-1.5 py-0.5 text-[10px] font-medium text-text-muted">
            Esc
          </kbd>
        </div>
        <ul
          id="command-palette-results"
          role="listbox"
          aria-label="Results"
          className="max-h-80 overflow-y-auto py-1"
        >
          {results.length === 0 && <li className="px-4 py-6 text-center text-sm text-text-muted">No matches</li>}
          {results.map((r, i) => {
            const showGroup = r.group !== lastGroup;
            lastGroup = r.group;
            const active = i === highlighted;
            return (
              <li key={r.key} role="none">
                {showGroup && (
                  <p className="px-4 pb-1 pt-2.5 text-label" role="presentation">
                    {r.group}
                  </p>
                )}
                <div role="option" id={`command-result-${i}`} aria-selected={active}>
                  <button
                    type="button"
                    tabIndex={-1}
                    onClick={() => choose(r)}
                    onPointerEnter={() => setHighlighted(i)}
                    className={cx(
                      "flex w-full items-center justify-between gap-3 px-4 py-2 text-left text-sm transition-colors duration-100",
                      active ? "bg-selected text-text-primary" : "text-text-secondary",
                    )}
                  >
                    <span className="flex min-w-0 items-baseline gap-2">
                      <span className="truncate font-medium">{r.label}</span>
                      {r.sublabel && <span className="shrink-0 text-code text-text-muted">{r.sublabel}</span>}
                    </span>
                    <span className="shrink-0 rounded bg-surface-sunken px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-text-muted">
                      {r.kind}
                    </span>
                  </button>
                </div>
              </li>
            );
          })}
        </ul>
      </div>
    </div>
  );
}
