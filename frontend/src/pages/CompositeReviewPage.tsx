import { useEffect, useState } from "react";
import { fetchCompositeCandidates, reviewCompositeCandidate } from "../api";
import CompositeReviewQueue from "../components/CompositeReviewQueue";
import LoadingState from "../components/LoadingState";
import type { CompositeCandidate, ReviewStatus } from "../types";

export default function CompositeReviewPage() {
  const [reviewStatus, setReviewStatus] = useState<ReviewStatus>("PENDING");
  const [candidates, setCandidates] = useState<CompositeCandidate[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = (status: ReviewStatus) => {
    fetchCompositeCandidates(status)
      .then((r) => setCandidates(r.candidates))
      .catch((e) => setError(String(e)));
  };

  useEffect(() => {
    load(reviewStatus);
  }, [reviewStatus]);

  const handleReview = async (id: number, decision: "approve" | "reject", reviewedBy: string, note?: string) => {
    await reviewCompositeCandidate(id, decision, reviewedBy, note);
    load(reviewStatus);
  };

  if (error) return <div className="p-6 text-red-600">Failed to load composite candidates: {error}</div>;
  if (!candidates) return <LoadingState label="Loading composite candidates…" />;

  return (
    <CompositeReviewQueue
      candidates={candidates}
      reviewStatus={reviewStatus}
      onReviewStatusChange={setReviewStatus}
      onReview={handleReview}
    />
  );
}
