import { useState } from "react";
import BulkApproveBar from "./BulkApproveBar";
import EmptyState from "./EmptyState";
import { ReviewShell, ReviewerField } from "./ReviewShell";
import { useReviewerGate } from "../lib/reviewer";
import { Alert, Badge, Button, Checkbox, SearchInput, type Tone } from "../ui";
import { IconCheckCircle, IconInbox } from "./icons";
import { matchesQuery } from "../lib/search";
import type { CapabilityStatus, TeacherCapabilityCandidate } from "../types";

interface Props {
  candidates: TeacherCapabilityCandidate[];
  capabilityStatus: CapabilityStatus;
  onStatusChange: (status: CapabilityStatus) => void;
  onReview: (id: number, decision: "approve" | "reject", reviewedBy: string, note?: string) => Promise<void>;
  onBulkApprove: (
    ids: number[],
    reviewedBy: string,
    note?: string,
  ) => Promise<{ approved_count: number; approved_ids: number[]; missing_ids: number[]; already_reviewed_ids: number[] }>;
}

const TABS: { value: CapabilityStatus; label: string }[] = [
  { value: "REVIEW_REQUIRED", label: "Review required" },
  { value: "ELIGIBLE", label: "Eligible" },
  { value: "NOT_ELIGIBLE", label: "Not eligible" },
];

const STATUS_META: Record<CapabilityStatus, { label: string; tone: Tone }> = {
  REVIEW_REQUIRED: { label: "Blocked pending human confirmation", tone: "critical" },
  ELIGIBLE: { label: "Eligible", tone: "success" },
  NOT_ELIGIBLE: { label: "Not eligible", tone: "neutral" },
};

export default function TeacherCapabilityQueue({ candidates, capabilityStatus, onStatusChange, onReview, onBulkApprove }: Props) {
  const reviewer = useReviewerGate();
  const [busyId, setBusyId] = useState<number | null>(null);
  const [query, setQuery] = useState("");
  const [actionError, setActionError] = useState<string | null>(null);
  // Unlike room-type's 100%-consistency signal, lesson_count has no clean
  // confidence cutoff in the real distribution, so there is no auto-selected
  // "high confidence" set here - a human ticks exactly the rows they agree
  // with, same "what was confirmed in the UI is exactly what gets written"
  // discipline as the room-type bulk-approve.
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
  const filtered = candidates.filter((c) => matchesQuery(query, [c.teacher_code, c.subject_code, c.faculty_code, c.notes]));
  const selectedInFilter = filtered.filter((c) => selectedIds.has(c.id));
  const allFilteredSelected = filtered.length > 0 && selectedInFilter.length === filtered.length;

  const toggleSelected = (id: number) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const toggleSelectAllFiltered = () => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (allFilteredSelected) {
        for (const c of filtered) next.delete(c.id);
      } else {
        for (const c of filtered) next.add(c.id);
      }
      return next;
    });
  };

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
      icon={<IconCheckCircle className="h-5 w-5" />}
      title="Teacher Capabilities"
      description="Permission to teach, per subject - docs/roadmap-v2.md 2.2. Bootstrapped from who currently teaches what in the real timetable, as a candidate for review, never asserted as fact: a currently-observed pairing starts Review required, not automatically Eligible. Confirming a teacher here unblocks teacher_not_qualified_for_class findings and (once built) teacher-reassignment suggestions for class_teacher_inconsistency."
      panelId="teacher-capabilities-panel"
      tabs={TABS.map((t) => ({ id: t.value, label: t.label }))}
      tabValue={capabilityStatus}
      onTabChange={onStatusChange}
      actions={<ReviewerField error={reviewer.error} />}
      search={
        <SearchInput
          value={query}
          onChange={setQuery}
          placeholder="Search teacher, subject, or faculty…"
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

      {capabilityStatus === "REVIEW_REQUIRED" && (
        <BulkApproveBar
          count={selectedInFilter.length}
          label="hand-checked"
          reviewedBy={reviewer.reviewer}
          onConfirm={async (who, note) => {
            const result = await onBulkApprove(selectedInFilter.map((c) => c.id), who, note);
            setSelectedIds(new Set());
            return result;
          }}
        />
      )}

      {candidates.length === 0 ? (
        <EmptyState
          icon={<IconInbox className="h-8 w-8" />}
          title={`Nothing ${TABS.find((t) => t.value === capabilityStatus)?.label.toLowerCase()}`}
        />
      ) : filtered.length === 0 ? (
        <EmptyState icon={<IconInbox className="h-8 w-8" />} title="No candidates match your search" />
      ) : (
        <div className="flex flex-col gap-2">
          {capabilityStatus === "REVIEW_REQUIRED" && (
            <Checkbox
              className="px-1"
              label={`Select all ${filtered.length} filtered`}
              checked={allFilteredSelected}
              indeterminate={!allFilteredSelected && selectedInFilter.length > 0}
              onChange={toggleSelectAllFiltered}
            />
          )}
          <ul className="flex flex-col gap-2">
            {filtered.map((c) => (
              <li
                key={c.id}
                className="rounded-lg border border-border bg-surface p-3 text-sm transition-colors duration-150 hover:border-border-strong"
              >
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <span className="flex min-w-0 items-center gap-2 font-medium text-text-primary">
                    {capabilityStatus === "REVIEW_REQUIRED" && (
                      <Checkbox
                        label={<span className="sr-only">Select {c.teacher_code}</span>}
                        checked={selectedIds.has(c.id)}
                        onChange={() => toggleSelected(c.id)}
                      />
                    )}
                    <span className="text-code">{c.teacher_code}</span>
                    <span className="text-text-muted">→</span>
                    <span className="text-code">{c.subject_code ?? c.faculty_code}</span>
                  </span>
                  <span className="flex items-center gap-2">
                    <span className="text-meta">{c.source_type}</span>
                    <Badge tone={STATUS_META[capabilityStatus].tone} size="sm" variant="outline">
                      {STATUS_META[capabilityStatus].label}
                    </Badge>
                  </span>
                </div>
                {c.notes && <div className="mt-1 text-meta">{c.notes}</div>}
                {capabilityStatus === "REVIEW_REQUIRED" && (
                  <div className="mt-2 flex gap-2">
                    <Button size="sm" variant="primary" loading={busyId === c.id} onClick={() => handleReview(c.id, "approve")}>
                      Qualified
                    </Button>
                    <Button size="sm" loading={busyId === c.id} onClick={() => handleReview(c.id, "reject")}>
                      Not qualified
                    </Button>
                  </div>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}
    </ReviewShell>
  );
}
