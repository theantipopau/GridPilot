import { IconSearch } from "./icons";

interface Props {
  value: string;
  onChange: (value: string) => void;
  placeholder: string;
  resultCount?: number;
  totalCount?: number;
}

// Shared across the review queues (Findings, Room Constraints, Teacher
// Capabilities, Composite Review) and Rooms - each of these lists real
// data grows into the hundreds (156 open findings, 199 room-constraint
// candidates, 213 teacher-capability candidates at real Sophia scale),
// and none of them had any way to narrow that down beyond a status tab.
// Client-side substring filtering, not a new endpoint - every one of
// these lists is already fetched in full, so there's nothing a server
// round-trip would add except latency.
export default function SearchBox({ value, onChange, placeholder, resultCount, totalCount }: Props) {
  const showCount = resultCount != null && totalCount != null && value.trim().length > 0;
  return (
    <div className="flex items-center gap-2">
      <div className="relative">
        <IconSearch className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-ink-muted" />
        <input
          type="text"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={placeholder}
          className="w-64 rounded-md border border-slate-300 py-1.5 pl-8 pr-7 text-sm text-slate-900"
        />
        {value && (
          <button
            type="button"
            onClick={() => onChange("")}
            aria-label="Clear search"
            className="absolute right-2 top-1/2 -translate-y-1/2 text-ink-muted hover:text-slate-600"
          >
            ✕
          </button>
        )}
      </div>
      {showCount && (
        <span className="text-xs text-ink-muted">
          {resultCount} of {totalCount}
        </span>
      )}
    </div>
  );
}
