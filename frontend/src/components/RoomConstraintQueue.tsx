import { useState } from "react";
import EmptyState from "./EmptyState";
import PageHeader from "./PageHeader";
import { IconDoor, IconInbox } from "./icons";
import type { ReviewStatus, RoomTypeConstraintCandidate } from "../types";

interface Props {
  candidates: RoomTypeConstraintCandidate[];
  reviewStatus: ReviewStatus;
  onReviewStatusChange: (status: ReviewStatus) => void;
  onReview: (id: number, decision: "approve" | "reject", reviewedBy: string, note?: string) => Promise<void>;
}

const TABS: ReviewStatus[] = ["PENDING", "APPROVED", "REJECTED"];

export default function RoomConstraintQueue({ candidates, reviewStatus, onReviewStatusChange, onReview }: Props) {
  const [reviewedBy, setReviewedBy] = useState("");
  const [busyId, setBusyId] = useState<number | null>(null);

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
        icon={<IconDoor className="h-5 w-5" />}
        title="Room Constraints"
        description="Which room_type each class actually needs, inferred from how it's already been scheduled - no
          subject-to-room mapping exists in the source export, so this is a proposal for review, not a fact.
          Approving a class here unblocks room_feature_mismatch findings for it and (eventually) narrows the room
          search a solver would consider - see docs/solver.md."
      />

      <div className="mb-4 flex items-center gap-3">
        <label className="text-sm text-slate-600">Reviewing as</label>
        <input
          type="text"
          value={reviewedBy}
          onChange={(e) => setReviewedBy(e.target.value)}
          placeholder="Your name"
          className="rounded-md border border-slate-300 px-2 py-1 text-sm"
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
      ) : (
        <div className="flex flex-col gap-2">
          {candidates.map((c) => {
            const ratio = c.matching_lesson_count / c.total_lesson_count;
            return (
              <div
                key={c.id}
                className="rounded-lg border border-slate-200 bg-white p-3 text-sm shadow-sm transition-shadow duration-150 hover:shadow-md"
              >
                <div className="flex items-center justify-between">
                  <span className="font-medium text-slate-900">
                    {c.class_code} <span className="mx-1 opacity-50">→</span> {c.room_type}
                  </span>
                  <span className="text-xs text-slate-400">
                    {c.matching_lesson_count}/{c.total_lesson_count} lessons ({ratio.toLocaleString(undefined, { style: "percent" })})
                  </span>
                </div>
                {c.reviewed_by && (
                  <div className="mt-1 text-xs text-slate-400">
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
                      Require {c.room_type}
                    </button>
                    <button
                      type="button"
                      disabled={busyId === c.id}
                      onClick={() => handleReview(c.id, "reject")}
                      className="rounded-md bg-slate-200 px-3 py-1 text-xs font-medium text-slate-700 transition-colors duration-150 hover:bg-slate-300 disabled:opacity-50"
                    >
                      Any room is fine
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
