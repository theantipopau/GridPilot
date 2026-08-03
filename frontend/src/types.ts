export type EntryKind = "REGISTRATION" | "LESSON_SLOT" | "BREAK";
export type EntryType =
  | "LESSON"
  | "BREAK"
  | "ASSEMBLY"
  | "GENERAL_PURPOSE"
  | "DETENTION"
  | "REGISTRATION"
  | "OTHER";

export interface Day {
  code: string;
  day_no: number;
  week_label: string;
}

export interface Period {
  code: string;
  name: string;
  day_code: string;
  period_no: number;
  start_time: string | null;
  finish_time: string | null;
  entry_kind: EntryKind;
}

export interface Room {
  code: string;
  name: string;
  seats: number | null;
  room_type: string | null;
}

export interface Teacher {
  code: string;
  first_name: string | null;
  last_name: string | null;
  staff_category: string | null;
}

export interface RollClass {
  code: string;
  year_level_code: string | null;
  is_support_roll_class: number;
}

export interface YearLevel {
  code: string;
}

export interface ReferenceData {
  days: Day[];
  periods: Period[];
  rooms: Room[];
  teachers: Teacher[];
  roll_classes: RollClass[];
  year_levels: YearLevel[];
}

export interface TimetableEntry {
  day_code: string;
  day_no: number;
  week_label: string;
  period_code: string;
  period_no: number;
  period_name: string;
  entry_kind: EntryKind;
  entry_type: EntryType;
  class_code: string | null;
  class_name: string | null;
  subject_name: string | null;
  room_code: string | null;
  room_name: string | null;
  teacher_code: string | null;
  teacher_first_name: string | null;
  teacher_last_name: string | null;
  roll_class_code: string;
}

export type ViewType = "teacher" | "room" | "roll_class";

export interface TimetableResponse {
  view: ViewType;
  code: string;
  label: string;
  entries: TimetableEntry[];
}

export type Severity = "info" | "warning" | "critical";

export interface EntityRef {
  type: "teacher" | "room" | "class" | "student" | "roll_class" | "composite_group";
  code: string;
}

export interface SlotRef {
  day_code: string;
  period_code: string;
}

export interface Finding {
  id: number;
  rule_id: string;
  severity: Severity;
  title: string;
  entity_refs: EntityRef[];
  slot_refs: SlotRef[];
  evidence: Record<string, unknown>;
  status: string;
  computed_at: string;
}

export interface FindingsResponse {
  findings: Finding[];
  total: number;
  counts_by_severity: Record<Severity, number>;
}

export type ReviewStatus = "PENDING" | "APPROVED" | "REJECTED";

export interface CompositeCandidate {
  id: number;
  teacher_code: string;
  room_code: string;
  class_codes: string[];
  review_status: ReviewStatus;
  slot_count: number;
  detected_at: string;
  reviewed_at: string | null;
  reviewed_by: string | null;
  review_note: string | null;
}

export interface TimetableEntryLookup {
  entry_id: number;
  day_code: string;
  period_code: string;
  class_code: string | null;
  room_code: string | null;
  teacher_code: string | null;
  roll_class_code: string;
}

export type ValidationStatus = "NOT_VALIDATED" | "VALID" | "INVALID";
export type ApprovalStatus = "DRAFT" | "APPROVED" | "REJECTED";

export interface FindingSummary {
  rule_id: string;
  severity: Severity;
  title: string;
}

export interface ValidationResult {
  valid: boolean;
  reason: string | null;
  introduced_findings: FindingSummary[];
  resolved_findings: FindingSummary[];
  unresolved_originating_findings: number[];
}

export interface ChangeSetSummary {
  id: number;
  name: string;
  description: string | null;
  validation_status: ValidationStatus;
  approval_status: ApprovalStatus;
  created_at: string;
  created_by: string;
  change_count: number;
}

export interface ChangeEndpoint {
  day_code: string | null;
  period_code: string | null;
  room_code: string | null;
  teacher_code: string | null;
}

export interface ProposedChange {
  id: number;
  timetable_entry_id: number;
  before: ChangeEndpoint;
  after: ChangeEndpoint;
  reason: string | null;
  finding_ids: number[];
}

export interface ChangeSetDetail extends ChangeSetSummary {
  validation_result: ValidationResult | null;
  validated_at: string | null;
  reviewed_at: string | null;
  reviewed_by: string | null;
  changes: ProposedChange[];
}

export interface SuggestionCandidate {
  entry_id: number;
  class_code: string | null;
  before: { day_code: string; period_code: string; room_code: string | null };
  after: { day_code: string; period_code: string; room_code: string | null };
  movement_cost: number;
  resolves_finding_count: number;
}

export interface SuggestionsResponse {
  finding_id: number;
  supported: boolean;
  note: string | null;
  candidates: SuggestionCandidate[];
}
