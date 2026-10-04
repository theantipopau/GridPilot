import { useState } from "react";
import EmptyState from "./EmptyState";
import PageHeader from "./PageHeader";
import SearchBox from "./SearchBox";
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
  const [reviewedBy, setReviewedBy] = useState("");
  const [busyId, setBusyId] = useState<number | null>(null);
  const [query, setQuery] = useState("");
  const filtered = candidates.filter((c) =>
    matchesQuery(query, [displayName(c), c.subject_code, c.assigned_teacher_code, c.assigned_room_code]),
  );

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
        icon={<IconClipboardList className="h-5 w-5" />}
        title="Teaching Requirements"
        description="What the school currently intends to run, bootstrapped from the resolved timetable - the demand
          model docs/roadmap-v3.md section 3.1 calls the biggest structural gap this project had. Each candidate is
          a proposal (periods per cycle, assigned teacher and room) read off the current schedule, never asserted as
          fact - a composite class collapses to one requirement for its whole group. Approving a requirement unblocks
          the teaching_requirement_blocking finding (no eligible teacher) and, eventually, allocation/blocking work."
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
          placeholder="Search class, subject, teacher, or room…"
          resultCount={filtered.length}
          totalCount={candidates.length}
        />
      </div>

      <div className="mb-4 flex gap-1 border-b border-slate-200">
        {TABS.map((tab) => (
          <button
            key={tab}
            type="button"
            onClick={() => onReviewStatusChange(tab)}
            className={`px-3 py-2 text-sm font-medium ${
              reviewStatus === tab
                ? "border-b-2 border-sky-600 text-sky-700"
                : "text-slate-500 hover:text-slate-700"
            }`}
          >
            {tab.charAt(0) + tab.slice(1).toLowerCase()}
          </button>
        ))}
      </div>

      {candidates.length === 0 ? (
        <EmptyState
          icon={<IconInbox className="h-8 w-8" />}
          title={`No ${reviewStatus.toLowerCase()} candidates`}
        />
      ) : filtered.length === 0 ? (
        <EmptyState icon={<IconInbox className="h-8 w-8" />} title="No candidates match your search" />
      ) : (
        <div className="flex flex-col gap-2">
          {filtered.map((c) => {
            const ratio = c.total_lesson_count > 0 ? c.matching_lesson_count / c.total_lesson_count : 0;
            return (
              <div
                key={c.id}
                className="rounded-lg border border-slate-200 bg-white p-3 text-sm shadow-sm transition-shadow duration-150 hover:shadow-md"
              >
                <div className="flex items-center justify-between">
                  <span className="font-medium text-slate-900">
                    {displayName(c)}
                    {c.subject_code && <span className="ml-2 text-xs font-normal text-ink-muted">{c.subject_code}</span>}
                  </span>
                  <span className="text-xs text-ink-muted">
                    {c.periods_per_cycle} period{c.periods_per_cycle === 1 ? "" : "s"}/cycle
                  </span>
                </div>
                <div className="mt-1 text-xs text-ink-muted">
                  {c.assigned_teacher_code ?? "no teacher"} · {c.assigned_room_code ?? "no room"} ·{" "}
                  {c.matching_lesson_count}/{c.total_lesson_count} lessons consistent (
                  {ratio.toLocaleString(undefined, { style: "percent" })})
                </div>
                {c.reviewed_by && (
                  <div className="mt-1 text-xs text-ink-muted">
                    Reviewed by {c.reviewed_by}{c.review_note ? ` - "${c.review_note}"` : ""}
                  </div>
                )}
                {reviewStatus === "PENDING" && (
                  <div className="mt-2 flex gap-2">
                    <button
                      type="button"
                      disabled={busyId === c.id}
                      onClick={() => handleReview(c.id, "approve")}
                      className="rounded-md bg-emerald-600 px-3 py-1 text-xs font-medium text-white transition-colors duration-150 hover:bg-emerald-700 disabled:opacity-50"
                    >
                      This is what we run
                    </button>
                    <button
                      type="button"
                      disabled={busyId === c.id}
                      onClick={() => handleReview(c.id, "reject")}
                      className="rounded-md bg-slate-200 px-3 py-1 text-xs font-medium text-slate-700 transition-colors duration-150 hover:bg-slate-300 disabled:opacity-50"
                    >
                      Not accurate
                    </button>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
