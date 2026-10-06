import { Badge, type Tone } from "../ui";
import type { ApprovalStatus, ValidationStatus } from "../types";

/** Change-set state in words first; the tone is only a backup signal. The
 *  same two badges appear in the list and the detail, so a draft reads as a
 *  draft everywhere (docs/design-system.md §status). */
const APPROVAL: Record<ApprovalStatus, { label: string; tone: Tone }> = {
  DRAFT: { label: "Draft", tone: "neutral" },
  APPROVED: { label: "Approved", tone: "success" },
  REJECTED: { label: "Rejected", tone: "neutral" },
};

const VALIDATION: Record<ValidationStatus, { label: string; tone: Tone }> = {
  VALID: { label: "Validated", tone: "success" },
  INVALID: { label: "Invalid", tone: "critical" },
  NOT_VALIDATED: { label: "Not validated", tone: "neutral" },
};

export function ApprovalBadge({ status }: { status: ApprovalStatus }) {
  const { label, tone } = APPROVAL[status] ?? { label: status, tone: "neutral" as Tone };
  return <Badge tone={tone} size="sm" title={label}>{label}</Badge>;
}

export function ValidationBadge({ status }: { status: ValidationStatus }) {
  const { label, tone } = VALIDATION[status] ?? { label: status, tone: "neutral" as Tone };
  return <Badge tone={tone} variant="outline" size="sm" title={label}>{label}</Badge>;
}
