import { useState } from "react";
import type { ChangeEndpoint, ChangeSetDetail as ChangeSetDetailType, ReferenceData } from "../types";
import AddChangeForm from "./AddChangeForm";
import ExportPreviewPanel from "./ExportPreviewPanel";
import { ApprovalBadge, ValidationBadge } from "./ChangeSetStatus";
import { ReviewerField } from "./ReviewShell";
import { useReviewerGate } from "../lib/reviewer";
import { Alert, Badge, Button, DetailSection, EmptyState } from "../ui";
import { IconGitBranch } from "./icons";

interface Prefill {
  day_code?: string;
  period_code?: string;
  teacher_code?: string;
  room_code?: string;
  class_code?: string;
  finding_id?: number;
}

export interface AddChangeParams {
  timetable_entry_id: number;
  after_day_code?: string;
  after_period_code?: string;
  after_room_code?: string;
  after_teacher_code?: string;
  reason?: string;
  finding_ids?: number[];
}

interface Props {
  changeSet: ChangeSetDetailType;
  reference: ReferenceData;
  prefill?: Prefill;
  onAddChange: (params: AddChangeParams) => Promise<void>;
  onRemoveChange: (changeId: number) => Promise<void>;
  onValidate: () => Promise<void>;
  onApprove: (reviewedBy: string) => Promise<void>;
  onReject: (reviewedBy: string) => Promise<void>;
}

/** "Day P / room / teacher" in code type - the same way a slot reads in the
 *  grid, so a before line and a proposed line are comparable at a glance. */
function Endpoint({ value }: { value: ChangeEndpoint }) {
  const day = value.day_code ?? "-";
  const period = value.period_code ?? "-";
  const room = value.room_code ?? "-";
  const teacher = value.teacher_code ?? "-";
  return (
    <span className="nums text-code">
      {day} {period} <span className="text-text-muted">/</span> {room} <span className="text-text-muted">/</span>{" "}
      {teacher}
    </span>
  );
}

export default function ChangeSetDetail({
  changeSet, reference, prefill, onAddChange, onRemoveChange, onValidate, onApprove, onReject,
}: Props) {
  const reviewer = useReviewerGate();
  const [busy, setBusy] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  const run = async (fn: () => Promise<void>) => {
    setBusy(true);
    setActionError(null);
    try {
      await fn();
    } catch (e) {
      setActionError(String(e));
    } finally {
      setBusy(false);
    }
  };

  const decide = (decision: "approve" | "reject") => {
    if (!reviewer.check()) return;
    run(() => (decision === "approve" ? onApprove(reviewer.reviewer) : onReject(reviewer.reviewer)));
  };

  const isDraft = changeSet.approval_status === "DRAFT";
  const result = changeSet.validation_result;

  return (
    <div className="flex flex-col gap-4">
      {actionError && (
        <Alert tone="critical" onDismiss={() => setActionError(null)}>
          {actionError}
        </Alert>
      )}

      <header className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <h2 className="text-section-title">{changeSet.name}</h2>
          {changeSet.description && <p className="mt-0.5 text-body text-text-secondary">{changeSet.description}</p>}
          <div className="mt-2 flex flex-wrap items-center gap-1.5">
            <ValidationBadge status={changeSet.validation_status} />
            <ApprovalBadge status={changeSet.approval_status} />
            <span className="nums text-meta">
              {changeSet.changes.length} change{changeSet.changes.length === 1 ? "" : "s"}
            </span>
          </div>
        </div>
      </header>

      <DetailSection
        title="Proposed changes"
        description="Left is the timetable as imported; right is what approval would record. The source export is never edited."
        aside={<span className="nums">{changeSet.changes.length}</span>}
        headingLevel={2}
      >
        {changeSet.changes.length === 0 ? (
          <EmptyState
            icon={<IconGitBranch className="h-7 w-7" />}
            title="No changes yet"
            description="Add one below, or propose a fix from a finding."
          />
        ) : (
          <ul className="flex flex-col gap-2">
            {changeSet.changes.map((c) => (
              <li
                key={c.id}
                className="rounded-lg border border-border bg-surface p-3 transition-colors duration-150 hover:border-border-strong"
              >
                <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
                  <div className="min-w-0 rounded-md border border-border bg-surface-sunken px-2 py-1">
                    <span className="mr-2 text-label text-text-muted">NOW</span>
                    <Endpoint value={c.before} />
                  </div>
                  <span aria-hidden="true" className="text-timetable-proposed">
                    &rarr;
                  </span>
                  <div className="min-w-0 rounded-md border border-dashed border-timetable-proposed bg-timetable-proposed-surface px-2 py-1">
                    <span className="mr-2 text-label text-timetable-proposed">PROPOSED</span>
                    <Endpoint value={c.after} />
                  </div>
                  {isDraft && (
                    <div className="ml-auto">
                      <Button
                        size="sm"
                        variant="ghost"
                        loading={busy}
                        onClick={() => run(() => onRemoveChange(c.id))}
                      >
                        Remove
                      </Button>
                    </div>
                  )}
                </div>
                {c.reason && <p className="mt-2 text-meta">{c.reason}</p>}
                {c.finding_ids.length > 0 && (
                  <div className="mt-2 flex flex-wrap items-center gap-1.5">
                    <span className="text-label text-text-muted">ADDRESSES</span>
                    {c.finding_ids.map((id) => (
                      <Badge key={id} size="sm" variant="outline" tone="info">
                        finding {id}
                      </Badge>
                    ))}
                  </div>
                )}
              </li>
            ))}
          </ul>
        )}
      </DetailSection>

      {isDraft && <AddChangeForm reference={reference} prefill={prefill} onSubmit={onAddChange} />}

      {result && (
        <DetailSection
          title="Validation result"
          description={result.reason ?? undefined}
          headingLevel={2}
        >
          <div className="flex flex-col gap-2">
            {result.resolved_findings.length > 0 && (
              <Alert tone="success" title={`Resolves ${result.resolved_findings.length} existing finding(s)`}>
                <ul className="ml-4 list-disc space-y-0.5">
                  {result.resolved_findings.map((f, i) => (
                    <li key={i}>{f.title}</li>
                  ))}
                </ul>
              </Alert>
            )}
            {result.introduced_findings.length > 0 && (
              <Alert tone="critical" title={`Introduces ${result.introduced_findings.length} new finding(s)`}>
                <ul className="ml-4 list-disc space-y-0.5">
                  {result.introduced_findings.map((f, i) => (
                    <li key={i}>{f.title}</li>
                  ))}
                </ul>
              </Alert>
            )}
            {result.resolved_findings.length === 0 && result.introduced_findings.length === 0 && (
              <p className="text-body text-text-secondary">
                Validation finished with no resolved and no introduced findings.
              </p>
            )}
          </div>
        </DetailSection>
      )}

      {isDraft && (
        <div className="grid gap-3 md:grid-cols-2">
          <DetailSection
            title="1. Test the draft"
            description="Runs the clash rules against this change set. Testing never records a decision."
            headingLevel={2}
          >
            <Button
              variant="secondary"
              loading={busy}
              disabled={changeSet.changes.length === 0}
              onClick={() => run(onValidate)}
            >
              Validate
            </Button>
            {changeSet.changes.length === 0 && (
              <p className="mt-2 text-meta">Add at least one proposed change to validate.</p>
            )}
          </DetailSection>

          <DetailSection
            title="2. Record a decision"
            description="Approval creates a durable audit record. The imported timetable stays untouched."
            headingLevel={2}
          >
            <ReviewerField error={reviewer.error} className="mb-3 w-full" />
            <div className="flex flex-wrap gap-2">
              <Button
                variant="primary"
                loading={busy}
                disabled={changeSet.validation_status !== "VALID"}
                title={
                  changeSet.validation_status !== "VALID"
                    ? "Validation must pass before this set can be approved"
                    : undefined
                }
                onClick={() => decide("approve")}
              >
                Approve
              </Button>
              <Button variant="secondary" loading={busy} onClick={() => decide("reject")}>
                Reject
              </Button>
            </div>
            {changeSet.validation_status !== "VALID" && (
              <p className="mt-2 text-meta">Approving unlocks once validation passes.</p>
            )}
          </DetailSection>
        </div>
      )}

      {changeSet.approval_status === "APPROVED" && (
        <>
          <Alert tone="success" title="Approved">
            {changeSet.reviewed_by && <span>By {changeSet.reviewed_by}</span>}
            {changeSet.reviewed_at && <span> on {changeSet.reviewed_at}</span>}
            {". The source timetable is unchanged - this record is the durable approval."}
          </Alert>
          <ExportPreviewPanel changeSetId={changeSet.id} />
        </>
      )}

      {changeSet.approval_status === "REJECTED" && (
        <Alert tone="neutral" title="Rejected">
          {changeSet.reviewed_by && <span>By {changeSet.reviewed_by}</span>}
          {changeSet.reviewed_at && <span> on {changeSet.reviewed_at}</span>}
          {". The proposed changes remain visible for reference; the source timetable is unchanged."}
        </Alert>
      )}
    </div>
  );
}
