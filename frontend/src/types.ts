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
  faculty_code: string | null;
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
  reviewed_at: string | null;
  reviewed_by: string | null;
  review_note: string | null;
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

export interface RoomTypeConstraintCandidate {
  id: number;
  class_code: string;
  room_type: string;
  matching_lesson_count: number;
  total_lesson_count: number;
  review_status: ReviewStatus;
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
  before: { day_code: string; period_code: string; room_code: string | null; teacher_code: string | null };
  after: { day_code: string; period_code: string; room_code: string | null; teacher_code: string | null };
  movement_cost: number;
  resolves_finding_count: number;
  why: {
    no_new_clash: boolean;
    room_capacity: { confirmed: false } | { confirmed: true; seats: number; enrolled: number };
    capability_status: "ELIGIBLE" | "NOT_ELIGIBLE" | "REVIEW_REQUIRED" | null;
  };
  class_room_familiarity: { same_room_elsewhere_count: number; total_other_lessons: number } | null;
  class_teacher_familiarity: { same_teacher_elsewhere_count: number; total_other_lessons: number } | null;
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

export interface BlockingLineCourse {
  class_name_code: string | null;
  teacher_code: string | null;
  room_code: string | null;
  enrolled_count: number | null;
}

export interface BlockingLineClassGroup {
  roll_class_code: string;
  periods_per_cycle: number | null;
  courses: BlockingLineCourse[];
}

export interface BlockingLine {
  id: number;
  default_code: string;
  line: string;
  code: string | null;
  name: string | null;
  class_groups: BlockingLineClassGroup[];
  open_finding_count: number;
}

export interface BlockingGroup {
  group: string;
  lines: BlockingLine[];
}

export interface BlockingLinesResponse {
  groups: BlockingGroup[];
}

export type RepairStatus = "SOLVED" | "PARTIAL" | "INFEASIBLE" | "NO_MOVABLE_ENTRIES";

export interface RepairFindingRef {
  id: number;
  title: string | null;
}

export interface RepairNotEligible {
  finding_id: number;
  rule_id: string;
  reason: string;
}

export interface RepairResult {
  status: RepairStatus;
  change_set_id: number | null;
  moved_count: number;
  movable_entry_count: number;
  solve_time_seconds: number;
  findings_resolved: RepairFindingRef[];
  findings_unresolved: RepairFindingRef[];
  not_eligible: RepairNotEligible[];
}

export type AgreementSector = "SECONDARY" | "PRIMARY";
export type LeadershipTier = "MIDDLE" | "SENIOR";

export interface AgreementLoadRule {
  id: number;
  sector: AgreementSector;
  ordinary_hours_per_week: number;
  max_contact_hours_per_week: number;
  prep_correction_pct: number | null;
  max_cover_periods_per_year: number | null;
  contact_entry_types: string[] | null;
  clause_reference: string | null;
}

export interface AgreementLeadershipBand {
  id: number;
  tier: LeadershipTier;
  enrolment_min: number;
  enrolment_max: number;
  units: number | null;
  hours_per_year: number | null;
  release_fte: number | null;
  clause_reference: string | null;
}

export interface IndustrialAgreement {
  id: number;
  name: string;
  source_reference: string | null;
  effective_from: string;
  effective_to: string | null;
  confirmed_by: string | null;
  confirmed_at: string | null;
  load_rules: AgreementLoadRule[];
  leadership_bands: AgreementLeadershipBand[];
}

export interface EnrolmentDeclaration {
  id: number;
  planning_year: string;
  official_enrolment: number;
  as_at_date: string | null;
  entered_by: string;
  note: string | null;
}

export interface LeadershipPool {
  agreement_name: string | null;
  enrolment: number | null;
  tier: LeadershipTier;
  units: number | null;
  hours_per_year: number | null;
  release_fte: number | null;
  band_min: number | null;
  band_max: number | null;
}

export interface AllocatedRelease {
  teacher_code: string;
  role_name: string;
  release_minutes_per_cycle: number;
}

export interface ReleaseReconciliation {
  planning_year: string | null;
  middle_pool: LeadershipPool;
  senior_pool: LeadershipPool;
  allocated: AllocatedRelease[];
  total_allocated_minutes_per_cycle: number;
}

export type CapabilityStatus = "ELIGIBLE" | "NOT_ELIGIBLE" | "REVIEW_REQUIRED";

export interface TeacherCapabilityCandidate {
  id: number;
  teacher_code: string;
  faculty_code: string | null;
  subject_code: string | null;
  capability_status: CapabilityStatus;
  source_type: string;
  notes: string | null;
  effective_from: string;
  effective_to: string | null;
  created_at: string;
  updated_at: string;
}

export interface RoomPoolMembership {
  pool_code: string;
  room_codes: string[];
}

export interface RoomSummary {
  code: string;
  name: string;
  seats: number | null;
  room_type: string | null;
  used_slots: number;
  total_lesson_slots: number;
  utilisation_pct: number | null;
  pool: RoomPoolMembership | null;
  expected_class_codes: string[];
  open_finding_count: number;
}
