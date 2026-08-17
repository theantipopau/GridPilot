import type { ReferenceData, ViewType } from "../types";

interface Props {
  reference: ReferenceData;
  view: ViewType;
  code: string;
  onChange: (view: ViewType, code: string) => void;
}

const VIEW_OPTIONS: { value: ViewType; label: string }[] = [
  { value: "teacher", label: "Teacher" },
  { value: "room", label: "Room" },
  { value: "roll_class", label: "Roll class" },
];

/** The "view by X, pick a Y" controls for single-entity mode - bare
 * controls, no wrapping bar. Deliberately not its own bordered toolbar
 * row (that was `FilterBar`, since folded in here): stacking a second
 * full-width bordered bar under the mode-toggle toolbar was exactly the
 * "three separate bordered blocks" docs/roadmap-v2.md 4.3 flagged.
 * TimetablePage renders this inline in the one toolbar row instead. */
export default function EntityPicker({ reference, view, code, onChange }: Props) {
  const handleViewChange = (nextView: ViewType) => {
    const firstCode = codeOptionsFor(reference, nextView)[0]?.value ?? "";
    onChange(nextView, firstCode);
  };

  const options = codeOptionsFor(reference, view);

  return (
    <>
      <div>
        <label className="mb-1 block text-xs font-medium uppercase tracking-wide text-slate-500">View by</label>
        <select
          className="rounded-md border border-slate-300 px-3 py-1.5 text-sm text-slate-900"
          value={view}
          onChange={(e) => handleViewChange(e.target.value as ViewType)}
        >
          {VIEW_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>
      </div>
      <div>
        <label className="mb-1 block text-xs font-medium uppercase tracking-wide text-slate-500">
          {VIEW_OPTIONS.find((o) => o.value === view)?.label}
        </label>
        <select
          className="min-w-[220px] rounded-md border border-slate-300 px-3 py-1.5 text-sm text-slate-900"
          value={code}
          onChange={(e) => onChange(view, e.target.value)}
        >
          {options.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>
      </div>
    </>
  );
}

function codeOptionsFor(reference: ReferenceData, view: ViewType): { value: string; label: string }[] {
  if (view === "teacher") {
    return reference.teachers.map((t) => ({
      value: t.code,
      label: `${t.last_name}, ${t.first_name} (${t.code})`,
    }));
  }
  if (view === "room") {
    return reference.rooms.map((r) => ({ value: r.code, label: `${r.name} (${r.code})` }));
  }
  // roll_class - grouped visually by prefixing year level, since <select> here doesn't use optgroup markup
  return reference.roll_classes.map((rc) => ({
    value: rc.code,
    label: rc.year_level_code ? `Year ${rc.year_level_code} - ${rc.code}` : rc.code,
  }));
}
