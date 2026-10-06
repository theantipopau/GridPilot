import { useState } from "react";
import EmptyState from "./EmptyState";
import { ReviewShell, ReviewerField } from "./ReviewShell";
import { ReviewStatusBadge } from "./ReviewStatusBadge";
import { useReviewerGate } from "../lib/reviewer";
import { Alert, Button, SearchInput } from "../ui";
import { IconInbox, IconLayers } from "./icons";
import { matchesQuery } from "../lib/search";
import type { CompositeCandidate, ReviewStatus } from "../types";

interface Props {
  candidates: CompositeCandidate[];
  reviewStatus: ReviewStatus;
  onReviewStatusChange: (status: ReviewStatus) => void;
  onReview: (id: number, decision: "approve" | "reject", reviewedBy: string, note?: string) => Promise<void>;
}

/** Review state in words, with the tone only as backup. */
const TABS: ReviewStatus[] = ["PENDING", "APPROVED", "REJECTED"];

const REVIEW_STATUS_LABEL: Record<ReviewStatus, string> = {
  PENDING: "Under review",
  APPROVED: "Approved",
  REJECTED: "Rejected",
};

export default function CompositeReviewQueue({ candidates, reviewStatus, onReviewStatusChange, onReview }: Props) {
  const reviewer = useReviewerGate();
  const [busyId, setBusyId] = useState<number | null>(null);
  const [query, setQuery] = useState("");
  const [actionError, setActionError] = useState<string | null>(null);
  const filtered = candidates.filter((c) => matchesQuery(query, [...c.class_codes, c.teacher_code, c.room_code]));

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
      icon={<IconLayers className="h-5 w-5" />}
      title="Composite Review"
      description="Teacher+room combinations where the same physical lesson is scheduled under more than one official class code (e.g. two year levels merged into one class). Detection is a heuristic - approve only the ones that are genuinely one combined lesson. An approved group stops producing clash findings for those classes; a pending or rejected one still shows as a clash."
      panelId="composites-panel"
      tabs={TABS.map((t) => ({ id: t, label: REVIEW_STATUS_LABEL[t] }))}
      tabValue={reviewStatus}
      onTabChange={onReviewStatusChange}
      actions={<ReviewerField error={reviewer.error} />}
      search={
        <SearchInput
          value={query}
          onChange={setQuery}
          placeholder="Search class, teacher, or room…"
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

      {candidates.length === 0 ? (
        <EmptyState
          icon={<IconInbox className="h-8 w-8" />}
          title={`Nothing ${REVIEW_STATUS_LABEL[reviewStatus].toLowerCase()}`}
          description="Composite groups appear here once the rules engine detects them during import."
        />
      ) : filtered.length === 0 ? (
        <EmptyState icon={<IconInbox className="h-8 w-8" />} title="No candidates match your search" />
      ) : (
        <ul className="flex flex-col gap-2">
          {filtered.map((c) => (
            <li
              key={c.id}
              className="rounded-lg border border-border bg-surface p-3 text-sm transition-colors duration-150 hover:border-border-strong"
            >
              <div className="flex flex-wrap items-center justify-between gap-2">
                <span className="min-w-0 font-medium text-text-primary">
                  {c.class_codes.join(" + ")}
                  <span className="text-code ml-2 font-normal text-text-muted">
                    {c.teacher_code} in {c.room_code}
                  </span>
                </span>
                <span className="flex items-center gap-2">
                  <span className="nums text-meta">{c.slot_count} matching slots</span>
                  <ReviewStatusBadge status={c.review_status} />
                </span>
              </div>
              {c.reviewed_by && (
                <div className="mt-1 text-meta">
                  Reviewed by {c.reviewed_by}
                  {c.review_note ? ` - "${c.review_note}"` : ""}
                </div>
              )}
              {reviewStatus === "PENDING" && (
                <div className="mt-2 flex gap-2">
                  <Button size="sm" variant="primary" loading={busyId === c.id} onClick={() => handleReview(c.id, "approve")}>
                    Approve as one lesson
                  </Button>
                  <Button size="sm" loading={busyId === c.id} onClick={() => handleReview(c.id, "reject")}>
                    Not a composite
                  </Button>
                </div>
              )}
            </li>
          ))}
        </ul>
      )}
    </ReviewShell>
  );
}
