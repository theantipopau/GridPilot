import type {
  CompositeCandidate,
  FindingsResponse,
  ReferenceData,
  ReviewStatus,
  TimetableResponse,
  ViewType,
} from "./types";

const BASE = "/api";

async function getJson<T>(url: string): Promise<T> {
  const res = await fetch(url);
  if (!res.ok) {
    throw new Error(`Request failed (${res.status}): ${url}`);
  }
  return res.json() as Promise<T>;
}

async function postJson<T>(url: string, body: unknown): Promise<T> {
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    throw new Error(`Request failed (${res.status}): ${url}`);
  }
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
