import type { ReferenceData, TimetableResponse, ViewType } from "./types";

const BASE = "/api";

async function getJson<T>(url: string): Promise<T> {
  const res = await fetch(url);
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
