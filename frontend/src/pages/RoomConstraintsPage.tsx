import { useEffect, useState } from "react";
import { fetchRoomConstraintCandidates, reviewRoomConstraintCandidate } from "../api";
import RoomConstraintQueue from "../components/RoomConstraintQueue";
import LoadingState from "../components/LoadingState";
import type { ReviewStatus, RoomTypeConstraintCandidate } from "../types";

export default function RoomConstraintsPage() {
  const [reviewStatus, setReviewStatus] = useState<ReviewStatus>("PENDING");
  const [candidates, setCandidates] = useState<RoomTypeConstraintCandidate[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = (status: ReviewStatus) => {
    fetchRoomConstraintCandidates(status)
      .then((r) => setCandidates(r.candidates))
      .catch((e) => setError(String(e)));
  };

  useEffect(() => {
    load(reviewStatus);
  }, [reviewStatus]);

  const handleReview = async (id: number, decision: "approve" | "reject", reviewedBy: string, note?: string) => {
    await reviewRoomConstraintCandidate(id, decision, reviewedBy, note);
    load(reviewStatus);
  };

  if (error) return <div className="p-6 text-red-600">Failed to load room-constraint candidates: {error}</div>;
  if (!candidates) return <LoadingState label="Loading room-constraint candidates…" />;

  return (
    <RoomConstraintQueue
      candidates={candidates}
      reviewStatus={reviewStatus}
      onReviewStatusChange={setReviewStatus}
      onReview={handleReview}
    />
  );
}
