import { useState } from "react";
import EmptyState from "./EmptyState";
import { ReviewShell, ReviewerField } from "./ReviewShell";
import { ReviewStatusBadge } from "./ReviewStatusBadge";
import { useReviewerGate } from "../lib/reviewer";
import { Alert, Button, SearchInput } from "../ui";
import { IconClipboardList, IconInbox } from "./icons";
import { matchesQuery } from "../lib/search";
import type { ReviewStatus, TeachingRequirementCandidate } from "../types";

interface Props {
  candidates: TeachingRequirementCandidate[];
  reviewStatus: ReviewStatus;
  onReviewStatusChange: (status: ReviewStatus) => void;
  onReview: (id: number, decision: "approve" | "reject", reviewedBy: string, note?: string) => Promise<void>;
}

const TABS: ReviewStatus[] = ["PENDING", "APPROVED", "REJECTED"];

function displayName(c: TeachingRequirementCandidate): string {
  return c.member_class_codes ? c.member_class_codes.join(" + ") : (c.class_code ?? c.requirement_key);
}

export default function TeachingRequirementQueue({ candidates, reviewStatus, onReviewStatusChange, onReview }: Props) {
  const reviewer = useReviewerGate();
  const [busyId, setBusyId] = useState<number | null>(null);
  const [query, setQuery] = useState("");
  const [actionError, setActionError] = useState<string | null>(null);
  const filtered = candidates.filter((c) =>
    matchesQuery(query, [displayName(c), c.subject_code, c.assigned_teacher_code, c.assigned_room_code]),
  );

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
      icon={<IconClipboardList className="h-5 w-5" />}
      title="Teaching Requirements"
      description="What the school currently intends to run, bootstrapped from the resolved timetable - the demand model docs/roadmap-v3.md section 3.1 calls the biggest structural gap this project had. Each candidate is a proposal (periods per cycle, assigned teacher and room) read off the current schedule, never asserted as fact - a composite class collapses to one requirement for its whole group. Approving a requirement unblocks the teaching_requirement_blocking finding (no eligible teacher) and, eventually, allocation/blocking work."
      panelId="teaching-requirements-panel"
      tabs={TABS.map((t) => ({
        id: t,
        label: t === "PENDING" ? "Awaiting confirmation" : t === "APPROVED" ? "Confirmed" : "Rejected",
      }))}
      tabValue={reviewStatus}
      onTabChange={onReviewStatusChange}
      actions={<ReviewerField error={reviewer.error} />}
      search={
        <SearchInput
          value={query}
          onChange={setQuery}
          placeholder="Search class, subject, teacher, or room…"
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
          title="Nothing awaiting confirmation"
          description="Requirements are bootstrapped from the timetable when student-options files are imported."
        />
      ) : filtered.length === 0 ? (
        <EmptyState icon={<IconInbox className="h-8 w-8" />} title="No candidates match your search" />
      ) : (
        <ul className="flex flex-col gap-2">
          {filtered.map((c) => {
            const ratio = c.total_lesson_count > 0 ? c.matching_lesson_count / c.total_lesson_count : 0;
            return (
              <li
                key={c.id}
                className="rounded-lg border border-border bg-surface p-3 text-sm transition-colors duration-150 hover:border-border-strong"
              >
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <span className="font-medium text-text-primary">
                    {displayName(c)}
                    {c.subject_code && <span className="text-code ml-2 font-normal text-text-muted">{c.subject_code}</span>}
                  </span>
                  <span className="flex items-center gap-2">
                    <span className="nums text-meta">
                      {c.periods_per_cycle} period{c.periods_per_cycle === 1 ? "" : "s"}/cycle
                    </span>
                    <ReviewStatusBadge status={c.review_status} />
                  </span>
                </div>
                <div className="mt-1 text-meta">
                  <span className="text-code">{c.assigned_teacher_code ?? "no teacher"}</span> ·{" "}
                  <span className="text-code">{c.assigned_room_code ?? "no room"}</span> ·{" "}
                  <span className="nums">
                    {c.matching_lesson_count}/{c.total_lesson_count} lessons consistent (
                    {ratio.toLocaleString(undefined, { style: "percent" })})
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
                  <div className="mt-2 flex gap-2">
                    <Button size="sm" variant="primary" loading={busyId === c.id} onClick={() => handleReview(c.id, "approve")}>
                      This is what we run
                    </Button>
                    <Button size="sm" loading={busyId === c.id} onClick={() => handleReview(c.id, "reject")}>
                      Not accurate
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
