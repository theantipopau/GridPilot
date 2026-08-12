/** Faculty color coding for the timetable grids - the categorical
 * palette from the dataviz skill's validated default (8 hues, fixed
 * order, documented hex only - never a generated 9th). Re-validated
 * against this app's white surface:
 *   node scripts/validate_palette.js "<8 hexes>" --mode light --surface "#ffffff"
 *   -> all 8 pass; 3 slots (aqua/yellow/magenta) sit below 3:1 contrast
 *      and require a "relief" channel - satisfied here because every
 *      cell always shows its class code as visible text, never relies
 *      on color alone for identity.
 *
 * Only 10 of the school's ~19 faculties have any scheduled lessons at
 * all (checked against the real data), and the top 8 by lesson volume
 * cover 98.5% of faculty-tagged lessons - so those 8 get a fixed color
 * each; everything else (low-volume faculties, and the ~31% of lesson
 * entries with no faculty recorded at all in the source data - VET/
 * extension subjects mostly, see docs/data-formats.md) falls to a
 * neutral "Other" grey rather than a 9th generated hue, per the skill's
 * rule. The mapping is keyed by faculty CODE, fixed regardless of
 * volume in any given term's import - color follows the entity, not
 * its rank, so a re-ingest can't repaint which subject is which color. */

export const FACULTY_COLORS: Record<string, string> = {
  SCI: "#2a78d6", // blue
  Math: "#eb6834", // orange
  Eng: "#1baf7a", // aqua
  RE: "#eda100", // yellow
  DT: "#e87ba4", // magenta
  Arts: "#008300", // green
  PE: "#4a3aa7", // violet
  HUM: "#e34948", // red
};

export const FACULTY_COLOR_OTHER = "#898781"; // muted grey - low-volume or no-faculty entries

export function facultyColor(facultyCode: string | null): string {
  if (facultyCode && FACULTY_COLORS[facultyCode]) return FACULTY_COLORS[facultyCode];
  return FACULTY_COLOR_OTHER;
}

export const FACULTY_LEGEND: { code: string; label: string; color: string }[] = [
  { code: "SCI", label: "Science", color: FACULTY_COLORS.SCI },
  { code: "Math", label: "Mathematics", color: FACULTY_COLORS.Math },
  { code: "Eng", label: "English", color: FACULTY_COLORS.Eng },
  { code: "RE", label: "Religion", color: FACULTY_COLORS.RE },
  { code: "DT", label: "Design Tech", color: FACULTY_COLORS.DT },
  { code: "Arts", label: "Arts", color: FACULTY_COLORS.Arts },
  { code: "PE", label: "HPE", color: FACULTY_COLORS.PE },
  { code: "HUM", label: "Humanities", color: FACULTY_COLORS.HUM },
  { code: "OTHER", label: "Other / no faculty", color: FACULTY_COLOR_OTHER },
];
