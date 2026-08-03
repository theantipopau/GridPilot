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

export default function FilterBar({ reference, view, code, onChange }: Props) {
  const handleViewChange = (nextView: ViewType) => {
    const firstCode = codeOptionsFor(reference, nextView)[0]?.value ?? "";
    onChange(nextView, firstCode);
  };

  const options = codeOptionsFor(reference, view);

  return (
    <div className="flex flex-wrap items-end gap-4 border-b border-slate-200 bg-white px-6 py-4">
      <div>
        <label className="mb-1 block text-xs font-medium uppercase tracking-wide text-slate-500">
          View by
        </label>
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
    </div>
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
