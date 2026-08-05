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
  entry_id: number;
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

export interface AuditEvent {
  id: number;
  occurred_at: string;
  actor: string;
  event_type: string;
  entity_type: string | null;
  entity_id: string | null;
  summary: string;
  detail: Record<string, unknown> | null;
}

export interface ExportGateResult {
  passed: boolean;
  detail: Record<string, unknown>;
}

export interface ExportPreview {
  change_set_id: number;
  change_set_name: string;
  ready: boolean;
  gates: Record<string, ExportGateResult>;
  changelog: Array<{ proposed_change_id: number; timetable_index: number; before: unknown; after: unknown }>;
  written: boolean;
  output_files: string[];
}

export interface LastIngest {
  started_at: string;
  finished_at: string | null;
  tfx_source_path: string | null;
  source_file_id: string | null;
}

export interface IngestStatus {
  has_data: boolean;
  last_ingest: LastIngest | null;
}

export interface IngestDiscrepancy {
  check_name: string;
  severity: "info" | "warning" | "error";
  description: string;
}

export interface StaffRole {
  id: number;
  name: string;
  tier: string | null;
  release_minutes_per_cycle: number | null;
  notes?: string | null;
}

export interface TeacherSummary {
  code: string;
  first_name: string | null;
  last_name: string | null;
  staff_category: string | null;
  faculty_codes: string[];
  contracted_load_minutes: number | null;
  scheduled_load_minutes: number | null;
  role: StaffRole | null;
}

export interface DashboardData {
  counts: {
    teachers: number;
    rooms: number;
    roll_classes: number;
    students: number;
    class_names: number;
    lessons: number;
    days: number;
    periods_per_day: number;
  };
  findings_by_severity: Record<Severity, number>;
  composites_pending: number;
  change_sets_draft: number;
  room_utilisation_pct: number | null;
  last_rules_run_at: string | null;
}

export interface IngestUploadResult {
  counts: Record<string, number>;
  analysis: {
    findings_total: number;
    findings_by_rule: Record<string, number>;
    composite_sync: Record<string, number>;
  };
  discrepancies: IngestDiscrepancy[];
  tfx_filename: string;
  sfx_filenames: string[];
}
