import { useSyncExternalStore } from "react";

/** Whether the app animates. Defaults to following the operating system's
 *  "reduce motion" setting - the right default for anyone sensitive to
 *  motion - but the person using this can override it either way from the
 *  sidebar. That override matters here specifically: Windows turns
 *  animation effects off on a lot of managed and remote desktops, which
 *  would otherwise silently disable every animation in the app with no way
 *  back short of changing an OS setting they may not control.
 *
 *  The resolved answer is written to <html data-motion="full|reduce"> so
 *  CSS (index.css) and scripts read the same single source of truth. */

export type MotionPreference = "system" | "on" | "off";

const STORAGE_KEY = "gridpilot.motion";
const listeners = new Set<() => void>();

function systemWantsReducedMotion(): boolean {
  return typeof window !== "undefined" && window.matchMedia?.("(prefers-reduced-motion: reduce)").matches === true;
}

export function getMotionPreference(): MotionPreference {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    return stored === "on" || stored === "off" ? stored : "system";
  } catch {
    return "system"; // storage blocked - follow the system
  }
}

export function motionEnabled(): boolean {
  const pref = getMotionPreference();
  return pref === "on" || (pref === "system" && !systemWantsReducedMotion());
}

function apply(): void {
  document.documentElement.dataset.motion = motionEnabled() ? "full" : "reduce";
  listeners.forEach((l) => l());
}

export function setMotionPreference(pref: MotionPreference): void {
  try {
    if (pref === "system") localStorage.removeItem(STORAGE_KEY);
    else localStorage.setItem(STORAGE_KEY, pref);
  } catch {
    // Preference just won't persist across launches - it still applies now.
  }
  apply();
}

/** Call once at startup, before first render, so there's no flash of the
 *  wrong motion state. */
export function initMotion(): void {
  apply();
  window.matchMedia?.("(prefers-reduced-motion: reduce)").addEventListener("change", () => {
    if (getMotionPreference() === "system") apply();
  });
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function useMotionEnabled(): boolean {
  return useSyncExternalStore(subscribe, motionEnabled, () => true);
}

export function useMotionPreference(): MotionPreference {
  return useSyncExternalStore(subscribe, getMotionPreference, () => "system" as MotionPreference);
}

export function systemReducesMotion(): boolean {
  return systemWantsReducedMotion();
}
