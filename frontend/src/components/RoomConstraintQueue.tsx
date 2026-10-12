import { useState } from "react";
import BulkApproveBar from "./BulkApproveBar";
import EmptyState from "./EmptyState";
import { ReviewShell, ReviewerField } from "./ReviewShell";
import { ReviewStatusBadge } from "./ReviewStatusBadge";
import { useReviewerGate } from "../lib/reviewer";
import { Alert, Button, SearchInput } from "../ui";
import { IconDoor, IconInbox } from "./icons";
import { matchesQuery } from "../lib/search";
import type { ReviewStatus, RoomTypeConstraintCandidate } from "../types";

interface Props {
  candidates: RoomTypeConstraintCandidate[];
  reviewStatus: ReviewStatus;
  onReviewStatusChange: (status: ReviewStatus) => void;
  onReview: (id: number, decision: "approve" | "reject", reviewedBy: string, note?: string) => Promise<void>;
  onBulkApprove: (
    ids: number[],
    reviewedBy: string,
    note?: string,
  ) => Promise<{ approved_count: number; approved_ids: number[]; missing_ids: number[]; already_reviewed_ids: number[] }>;
}

const TABS: ReviewStatus[] = ["PENDING", "APPROVED", "REJECTED"];

const TAB_LABELS: Record<ReviewStatus, string> = {
  PENDING: "To confirm",
  APPROVED: "Room type required",
  REJECTED: "Any room is fine",
};

export default function RoomConstraintQueue({ candidates, reviewStatus, onReviewStatusChange, onReview, onBulkApprove }: Props) {
  const reviewer = useReviewerGate();
  const [busyId, setBusyId] = useState<number | null>(null);
  const [query, setQuery] = useState("");
  const [actionError, setActionError] = useState<string | null>(null);
  const filtered = candidates.filter((c) => matchesQuery(query, [c.class_code, c.room_type]));
  // real data showed 167 of 199 pending candidates sit at exactly 100%
  // consistency - the same clean signal room_type_constraints.py's own
  // detection heuristic already relies on, not an invented cutoff. Scoped to
  // the currently-searched set, so a filter narrows what a bulk approval can
  // touch too.
  const fullConfidenceIds = filtered
    .filter((c) => c.matching_lesson_count === c.total_lesson_count)
    .map((c) => c.id);

  const handleReview = async (id: number, decision: "approve" | "reject") => {
    if (!reviewer.check()) return;
    setBusyId(id);
    setActionError(null);
    try {
      await onReview(id, decision, reviewer.reviewer);
    } catch (e) {
      setActionError(String(e));
    } finally {
      setBusyId(null);
    }
  };

  return (
    <ReviewShell
      icon={<IconDoor className="h-5 w-5" />}
      title="Room Constraints"
      description="Which room_type each class actually needs, inferred from how it's already been scheduled - no subject-to-room mapping exists in the source export, so this is a proposal for review, not a fact. Approving a class here unblocks room_feature_mismatch findings for it and (eventually) narrows the room search a solver would consider - see docs/solver.md."
      panelId="room-constraints-panel"
      tabs={TABS.map((t) => ({ id: t, label: TAB_LABELS[t] }))}
      tabValue={reviewStatus}
      onTabChange={onReviewStatusChange}
      actions={<ReviewerField error={reviewer.error} />}
      search={
        <SearchInput
          value={query}
          onChange={setQuery}
          placeholder="Search class or room type…"
          resultCount={filtered.length}
          totalCount={candidates.length}
        />
      }
      count={`${filtered.length} of ${candidates.length}`}
    >
      {actionError && (
        <Alert tone="critical" className="mb-3" onDismiss={() => setActionError(null)}>
          {actionError}
        </Alert>
      )}

      {reviewStatus === "PENDING" && (
        <BulkApproveBar
          count={fullConfidenceIds.length}
          label="100% consistency"
          reviewedBy={reviewer.reviewer}
          onConfirm={(who, note) => onBulkApprove(fullConfidenceIds, who, note)}
        />
      )}

      {candidates.length === 0 ? (
        <EmptyState
          icon={<IconInbox className="h-8 w-8" />}
          title={`Nothing ${TAB_LABELS[reviewStatus].toLowerCase()}`}
          description="Room-type candidates are detected during import from how each class is currently scheduled."
        />
      ) : filtered.length === 0 ? (
        <EmptyState icon={<IconInbox className="h-8 w-8" />} title="No candidates match your search" />
      ) : (
        <ul className="flex flex-col gap-2">
          {filtered.map((c) => {
            const ratio = c.matching_lesson_count / c.total_lesson_count;
            return (
              <li
                key={c.id}
                className="rounded-lg border border-border bg-surface p-3 text-sm transition-colors duration-150 hover:border-border-strong"
              >
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <span className="font-medium text-text-primary">
                    {c.class_code} <span className="mx-1 text-text-muted">→</span>
                    <span className="text-code">{c.room_type}</span>
                  </span>
                  <span className="flex items-center gap-2">
                    <span className="nums text-meta">
                      {c.matching_lesson_count}/{c.total_lesson_count} lessons (
                      {ratio.toLocaleString(undefined, { style: "percent" })})
                    </span>
                    <ReviewStatusBadge status={c.review_status} />
                  </span>
                </div>
                {c.reviewed_by ? (
                  <div className="mt-1 text-meta">
                    Reviewed by {c.reviewed_by}
                    {c.review_note ? ` — "${c.review_note}"` : ""}
                  </div>
                ) : (
                  <p className="mt-1 text-xs text-text-muted">
                    No reviewer recorded for this decision yet.
                  </p>
                )}
                {reviewStatus === "PENDING" && (
                  <div className="mt-2 flex flex-wrap gap-2">
                    <Button size="sm" variant="primary" loading={busyId === c.id} onClick={() => handleReview(c.id, "approve")}>
                      Require {c.room_type}
                    </Button>
                    <Button size="sm" loading={busyId === c.id} onClick={() => handleReview(c.id, "reject")}>
                      Any room is fine
                    </Button>
                  </div>
                )}
              </li>
            );
          })}
        </ul>
      )}
    </ReviewShell>
  );
}
