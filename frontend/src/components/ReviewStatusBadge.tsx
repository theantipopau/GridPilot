import { StatusIndicator } from "../ui";
import type { Tone } from "../ui";
import type { ReviewStatus } from "../types";

/** Review state in words first; the tone is only a backup signal. */
const STATUS: Record<ReviewStatus, { label: string; tone: Tone }> = {
  PENDING: { label: "Under review", tone: "brand" },
  APPROVED: { label: "Approved", tone: "success" },
  REJECTED: { label: "Rejected", tone: "neutral" },
};

export function ReviewStatusBadge({ status, size = "sm" }: { status: ReviewStatus; size?: "sm" | "md" }) {
  const { label, tone } = STATUS[status];
  return <StatusIndicator tone={tone} size={size} label={label} title={label} />;
}
