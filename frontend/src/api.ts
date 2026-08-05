import type {
  AuditEvent,
  ChangeSetDetail,
  ChangeSetSummary,
  CompositeCandidate,
  ExportPreview,
  FindingsResponse,
  IngestStatus,
  IngestUploadResult,
  ReferenceData,
  ReviewStatus,
  SuggestionsResponse,
  TimetableEntryLookup,
  TimetableResponse,
  ValidationResult,
  ViewType,
} from "./types";

const BASE = "/api";

async function extractError(res: Response, url: string): Promise<string> {
  try {
    const body = await res.json();
    if (body?.detail) return String(body.detail);
  } catch {
    // fall through to generic message
  }
  return `Request failed (${res.status}): ${url}`;
}

async function getJson<T>(url: string): Promise<T> {
  const res = await fetch(url);
  if (!res.ok) throw new Error(await extractError(res, url));
  return res.json() as Promise<T>;
}

async function postJson<T>(url: string, body: unknown): Promise<T> {
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(await extractError(res, url));
  return res.json() as Promise<T>;
}

async function deleteJson<T>(url: string): Promise<T> {
  const res = await fetch(url, { method: "DELETE" });
  if (!res.ok) throw new Error(await extractError(res, url));
  return res.json() as Promise<T>;
}

export function fetchReference(): Promise<ReferenceData> {
  return getJson(`${BASE}/reference`);
}

export function fetchTimetable(view: ViewType, code: string): Promise<TimetableResponse> {
  return getJson(`${BASE}/timetable?view=${view}&code=${encodeURIComponent(code)}`);
}

export function fetchFindings(): Promise<FindingsResponse> {
  return getJson(`${BASE}/findings`);
}

export function fetchSuggestions(findingId: number): Promise<SuggestionsResponse> {
  return getJson(`${BASE}/findings/${findingId}/suggestions`);
}

export function fetchCompositeCandidates(reviewStatus?: ReviewStatus): Promise<{ candidates: CompositeCandidate[] }> {
  const qs = reviewStatus ? `?review_status=${reviewStatus}` : "";
  return getJson(`${BASE}/composites/candidates${qs}`);
}

export function reviewCompositeCandidate(
  id: number,
  decision: "approve" | "reject",
  reviewedBy: string,
  note?: string,
): Promise<{ id: number; review_status: ReviewStatus }> {
  return postJson(`${BASE}/composites/candidates/${id}/${decision}`, { reviewed_by: reviewedBy, note });
}

export function findTimetableEntries(filters: {
  day_code?: string;
  period_code?: string;
  teacher_code?: string;
  room_code?: string;
  class_code?: string;
}): Promise<{ entries: TimetableEntryLookup[] }> {
  const qs = new URLSearchParams(
    Object.entries(filters).filter(([, v]) => !!v) as [string, string][],
  ).toString();
  return getJson(`${BASE}/timetable-entries?${qs}`);
}

export function fetchChangeSets(): Promise<{ change_sets: ChangeSetSummary[] }> {
  return getJson(`${BASE}/change-sets`);
}

export function fetchChangeSet(id: number): Promise<ChangeSetDetail> {
  return getJson(`${BASE}/change-sets/${id}`);
}

export function createChangeSet(name: string, description: string | undefined, createdBy: string): Promise<{ id: number }> {
  return postJson(`${BASE}/change-sets`, { name, description, created_by: createdBy });
}

export function addProposedChange(
  changeSetId: number,
  params: {
    timetable_entry_id: number;
    after_day_code?: string;
    after_period_code?: string;
    after_room_code?: string;
    after_teacher_code?: string;
    reason?: string;
    finding_ids?: number[];
  },
): Promise<{ id: number }> {
  return postJson(`${BASE}/change-sets/${changeSetId}/changes`, params);
}

export function removeProposedChange(changeSetId: number, changeId: number): Promise<{ status: string }> {
  return deleteJson(`${BASE}/change-sets/${changeSetId}/changes/${changeId}`);
}

export function validateChangeSet(changeSetId: number): Promise<ValidationResult> {
  return postJson(`${BASE}/change-sets/${changeSetId}/validate`, {});
}

export function approveChangeSet(changeSetId: number, reviewedBy: string): Promise<{ approval_status: string }> {
  return postJson(`${BASE}/change-sets/${changeSetId}/approve`, { reviewed_by: reviewedBy });
}

export function rejectChangeSet(changeSetId: number, reviewedBy: string): Promise<{ approval_status: string }> {
  return postJson(`${BASE}/change-sets/${changeSetId}/reject`, { reviewed_by: reviewedBy });
}

export function fetchAuditEvents(eventType?: string): Promise<{ events: AuditEvent[]; total: number }> {
  const qs = eventType ? `?event_type=${encodeURIComponent(eventType)}` : "";
  return getJson(`${BASE}/audit${qs}`);
}

export function fetchExportPreview(changeSetId: number): Promise<ExportPreview> {
  return getJson(`${BASE}/change-sets/${changeSetId}/export-preview`);
}

export function fetchIngestStatus(): Promise<IngestStatus> {
  return getJson(`${BASE}/ingest/status`);
}

export async function uploadImport(tfxFile: File, sfxFiles: File[]): Promise<IngestUploadResult> {
  const form = new FormData();
  form.append("tfx_file", tfxFile);
  for (const f of sfxFiles) form.append("sfx_files", f);
  const url = `${BASE}/ingest/upload`;
  const res = await fetch(url, { method: "POST", body: form });
  if (!res.ok) throw new Error(await extractError(res, url));
  return res.json() as Promise<IngestUploadResult>;
}
