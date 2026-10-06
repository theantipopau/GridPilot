import type { Tone } from "./Badge";

/** Shared severity mapping so "critical" looks identical on the dashboard, a
 *  finding row, a grid cell and a queue count - one vocabulary, one colour. */
export function toneForSeverity(severity: string): Tone {
  if (severity === "critical") return "critical";
  if (severity === "warning") return "warning";
  if (severity === "info") return "info";
  return "neutral";
}

/** Review/queue state vocabulary used across Findings and the review queues.
 *  Every caller renders the label AND a tone - never colour alone. */
export type ReviewStateLabel =
  | "newly detected"
  | "under review"
  | "accepted risk"
  | "resolved by draft change"
  | "resolved"
  | "blocked pending human confirmation";

export function reviewStateTone(state: ReviewStateLabel): Tone {
  switch (state) {
    case "newly detected":
      return "info";
    case "under review":
      return "brand";
    case "accepted risk":
      return "warning";
    case "resolved by draft change":
      return "accent";
    case "resolved":
      return "success";
    case "blocked pending human confirmation":
      return "critical";
  }
}
