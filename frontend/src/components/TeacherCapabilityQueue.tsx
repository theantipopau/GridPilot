import { useState } from "react";
import BulkApproveBar from "./BulkApproveBar";
import EmptyState from "./EmptyState";
import PageHeader from "./PageHeader";
import SearchBox from "./SearchBox";
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

export default function TeacherCapabilityQueue({ candidates, capabilityStatus, onStatusChange, onReview, onBulkApprove }: Props) {
  const [reviewedBy, setReviewedBy] = useState("");
  const [busyId, setBusyId] = useState<number | null>(null);
  const [query, setQuery] = useState("");
  // docs/roadmap-v3.md 1.3: unlike room-type's 100%-consistency signal,
  // lesson_count has no clean confidence cutoff in the real distribution,
  // so there is no auto-selected "high confidence" set here - a human
  // ticks exactly the rows they agree with, same "what was confirmed in
  // the UI is exactly what gets written" discipline as the room-type
  // bulk-approve.
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
    if (!reviewedBy.trim()) {
      alert("Enter your name before reviewing a candidate.");
      return;
    }
    setBusyId(id);
    try {
      await onReview(id, decision, reviewedBy.trim());
    } finally {
      setBusyId(null);
    }
  };

  return (
    <div className="p-6">
      <PageHeader
        icon={<IconCheckCircle className="h-5 w-5" />}
        title="Teacher Capabilities"
        description="Permission to teach, per subject - docs/roadmap-v2.md 2.2. Bootstrapped from who currently teaches
          what in the real timetable, as a candidate for review, never asserted as fact: a currently-observed
          pairing starts Review required, not automatically Eligible. Confirming a teacher here unblocks
          teacher_not_qualified_for_class findings and (once built) teacher-reassignment suggestions for
          class_teacher_inconsistency."
      />

      <div className="mb-4 flex items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <label className="text-sm text-slate-600">Reviewing as</label>
          <input
            type="text"
            value={reviewedBy}
            onChange={(e) => setReviewedBy(e.target.value)}
            placeholder="Your name"
            className="rounded-md border border-slate-300 px-2 py-1 text-sm"
          />
        </div>
        <SearchBox
          value={query}
          onChange={setQuery}
          placeholder="Search teacher, subject, or faculty…"
          resultCount={filtered.length}
          totalCount={candidates.length}
        />
      </div>

      <div className="mb-4 flex gap-1 border-b border-slate-200">
        {TABS.map((tab) => (
          <button
            key={tab.value}
            type="button"
            onClick={() => onStatusChange(tab.value)}
            className={`px-3 py-2 text-sm font-medium ${
              capabilityStatus === tab.value
                ? "border-b-2 border-sky-600 text-sky-700"
                : "text-slate-500 hover:text-slate-700"
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {capabilityStatus === "REVIEW_REQUIRED" && (
        <BulkApproveBar
          count={selectedInFilter.length}
          label="hand-checked"
          reviewedBy={reviewedBy}
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
          title={`No candidates ${TABS.find((t) => t.value === capabilityStatus)?.label.toLowerCase()}`}
        />
      ) : filtered.length === 0 ? (
        <EmptyState icon={<IconInbox className="h-8 w-8" />} title="No candidates match your search" />
      ) : (
        <div className="flex flex-col gap-2">
          {capabilityStatus === "REVIEW_REQUIRED" && (
            <label className="flex items-center gap-2 px-1 text-xs text-ink-muted">
              <input type="checkbox" checked={allFilteredSelected} onChange={toggleSelectAllFiltered} />
              Select all {filtered.length} filtered
            </label>
          )}
          {filtered.map((c) => (
            <div
              key={c.id}
              className="rounded-lg border border-slate-200 bg-white p-3 text-sm shadow-sm transition-shadow duration-150 hover:shadow-md"
            >
              <div className="flex items-center justify-between">
                <span className="flex items-center gap-2 font-medium text-slate-900">
                  {capabilityStatus === "REVIEW_REQUIRED" && (
                    <input
                      type="checkbox"
                      checked={selectedIds.has(c.id)}
                      onChange={() => toggleSelected(c.id)}
                      aria-label={`Select ${c.teacher_code} x ${c.subject_code ?? c.faculty_code}`}
                    />
                  )}
                  {c.teacher_code} <span className="mx-1 opacity-50">→</span> {c.subject_code ?? c.faculty_code}
                </span>
                <span className="text-xs text-ink-muted">{c.source_type}</span>
              </div>
              {c.notes && <div className="mt-1 text-xs text-ink-muted">{c.notes}</div>}
              {capabilityStatus === "REVIEW_REQUIRED" && (
                <div className="mt-2 flex gap-2">
                  <button
                    type="button"
                    disabled={busyId === c.id}
                    onClick={() => handleReview(c.id, "approve")}
                    className="rounded-md bg-emerald-600 px-3 py-1 text-xs font-medium text-white transition-colors duration-150 hover:bg-emerald-700 disabled:opacity-50"
                  >
                    Qualified
                  </button>
                  <button
                    type="button"
                    disabled={busyId === c.id}
                    onClick={() => handleReview(c.id, "reject")}
                    className="rounded-md bg-slate-200 px-3 py-1 text-xs font-medium text-slate-700 transition-colors duration-150 hover:bg-slate-300 disabled:opacity-50"
                  >
                    Not qualified
                  </button>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
