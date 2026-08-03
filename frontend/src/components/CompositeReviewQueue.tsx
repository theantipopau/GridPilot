import { useState } from "react";
import type { CompositeCandidate, ReviewStatus } from "../types";

interface Props {
  candidates: CompositeCandidate[];
  reviewStatus: ReviewStatus;
  onReviewStatusChange: (status: ReviewStatus) => void;
  onReview: (id: number, decision: "approve" | "reject", reviewedBy: string, note?: string) => Promise<void>;
}

const TABS: ReviewStatus[] = ["PENDING", "APPROVED", "REJECTED"];

export default function CompositeReviewQueue({ candidates, reviewStatus, onReviewStatusChange, onReview }: Props) {
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
      <p className="mb-4 max-w-2xl text-sm text-slate-600">
        These are teacher+room combinations where the same physical lesson is scheduled under more than one
        official class code (e.g. two year levels merged into one class). Detection is a heuristic - approve
        only the ones that are genuinely one combined lesson. An approved group stops producing clash findings
        for those classes; a pending or rejected one still shows as a clash.
      </p>

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
        <p className="text-sm text-slate-400">No {reviewStatus.toLowerCase()} candidates.</p>
      ) : (
        <div className="flex flex-col gap-2">
          {candidates.map((c) => (
            <div key={c.id} className="rounded-lg border border-slate-200 bg-white p-3 text-sm">
              <div className="flex items-center justify-between">
                <span className="font-medium text-slate-900">{c.class_codes.join(" + ")}</span>
                <span className="text-xs text-slate-400">{c.slot_count} matching slots</span>
              </div>
              <div className="mt-1 text-xs text-slate-500">
                {c.teacher_code} in {c.room_code}
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
                    className="rounded-md bg-emerald-600 px-3 py-1 text-xs font-medium text-white disabled:opacity-50"
                  >
                    Approve
                  </button>
                  <button
                    type="button"
                    disabled={busyId === c.id}
                    onClick={() => handleReview(c.id, "reject")}
                    className="rounded-md bg-slate-200 px-3 py-1 text-xs font-medium text-slate-700 disabled:opacity-50"
                  >
                    Reject
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
