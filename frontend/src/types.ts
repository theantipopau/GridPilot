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
