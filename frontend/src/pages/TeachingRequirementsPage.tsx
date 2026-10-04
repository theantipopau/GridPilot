import { useEffect, useState } from "react";
import { fetchTeachingRequirementCandidates, reviewTeachingRequirementCandidate } from "../api";
import TeachingRequirementQueue from "../components/TeachingRequirementQueue";
import LoadingState from "../components/LoadingState";
import type { ReviewStatus, TeachingRequirementCandidate } from "../types";

export default function TeachingRequirementsPage() {
  const [reviewStatus, setReviewStatus] = useState<ReviewStatus>("PENDING");
  const [candidates, setCandidates] = useState<TeachingRequirementCandidate[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = (status: ReviewStatus) => {
    fetchTeachingRequirementCandidates(status)
      .then((r) => setCandidates(r.candidates))
      .catch((e) => setError(String(e)));
  };

  useEffect(() => {
    load(reviewStatus);
  }, [reviewStatus]);

  const handleReview = async (id: number, decision: "approve" | "reject", reviewedBy: string, note?: string) => {
    await reviewTeachingRequirementCandidate(id, decision, reviewedBy, note);
    load(reviewStatus);
  };

  if (error) return <div className="p-6 text-red-600">Failed to load teaching-requirement candidates: {error}</div>;
  if (!candidates) return <LoadingState label="Loading teaching-requirement candidates…" />;

  return (
    <TeachingRequirementQueue
      candidates={candidates}
      reviewStatus={reviewStatus}
      onReviewStatusChange={setReviewStatus}
      onReview={handleReview}
    />
  );
}
