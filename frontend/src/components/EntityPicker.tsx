import { Combobox, Select } from "../ui";
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

/** The "view by X, pick a Y" controls for single-entity mode - bare controls,
 *  no wrapping bar (stacking a second bordered toolbar under the mode toolbar
 *  was exactly the "three separate bordered blocks" the audit flagged).
 *  The entity list is a Combobox: 75 teachers and 51 rooms are past the point
 *  where a native select is a scroll marathon, and it stays fully keyboard
 *  operable (arrows, Enter, Escape). */
export default function EntityPicker({ reference, view, code, onChange }: Props) {
  const handleViewChange = (nextView: ViewType) => {
    const firstCode = codeOptionsFor(reference, nextView)[0]?.value ?? "";
    onChange(nextView, firstCode);
  };

  const options = codeOptionsFor(reference, view);
  const viewLabel = VIEW_OPTIONS.find((o) => o.value === view)?.label ?? "Entity";

  return (
    <>
      <Select
        containerClassName="w-40"
        label="View by"
        size="sm"
        options={VIEW_OPTIONS}
        value={view}
        onChange={(v) => handleViewChange(v as ViewType)}
      />
      <Combobox
        containerClassName="w-64"
        label={viewLabel}
        size="sm"
        options={options}
        value={code}
        onChange={(v) => onChange(view, v)}
        placeholder={`Search ${viewLabel.toLowerCase()}…`}
        emptyText="No match"
      />
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
  // roll_class - grouped visually by year level in the label, since the
  // combobox list has no optgroup markup.
  return reference.roll_classes.map((rc) => ({
    value: rc.code,
    label: rc.year_level_code ? `Year ${rc.year_level_code} - ${rc.code}` : rc.code,
  }));
}
