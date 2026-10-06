import { useState, useSyncExternalStore } from "react";

/** Who is making this decision.
 *
 *  Every review surface in GridPilot records a free-text actor (there is no
 *  auth model - docs/ui-ux-audit.md §1.9 counted six independent "your name"
 *  inputs with three different validation styles). This is the single store
 *  for it: typed once, remembered in localStorage under a stable key, kept in
 *  sync across every component that reads it, and still blank by default so
 *  nothing is ever attributed to someone who didn't type it. */

const STORAGE_KEY = "gridpilot.reviewer";
const listeners = new Set<() => void>();

function read(): string {
  try {
    return localStorage.getItem(STORAGE_KEY) ?? "";
  } catch {
    return ""; // storage blocked - the field still works, just not remembered
  }
}

let cached = typeof window !== "undefined" ? read() : "";

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function setReviewerName(name: string): void {
  cached = name;
  try {
    if (name) localStorage.setItem(STORAGE_KEY, name);
    else localStorage.removeItem(STORAGE_KEY);
  } catch {
    // Preference just won't persist - it still applies now.
  }
  listeners.forEach((l) => l());
}

export function getReviewerName(): string {
  return cached;
}

export function useReviewerName(): [string, (value: string) => void] {
  const value = useSyncExternalStore(
    subscribe,
    () => cached,
    () => cached,
  );
  return [value, setReviewerName];
}

/** The gate every mutating review action keeps: without a name nothing is
 *  written, and the caller shows this message inline instead of blocking the
 *  whole app with a native alert(). */
export const REVIEWER_REQUIRED = "Enter your name before recording a decision.";

export function useReviewerGate() {
  const [reviewer] = useReviewerName();
  const [failed, setFailed] = useState(false);
  const ready = reviewer.trim().length > 0;
  const check = () => {
    if (!ready) {
      setFailed(true);
      return false;
    }
    setFailed(false);
    return true;
  };
  return { reviewer: reviewer.trim(), check, error: failed && !ready ? REVIEWER_REQUIRED : null, ready };
}
