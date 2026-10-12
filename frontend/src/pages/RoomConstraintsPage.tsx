import { useEffect, useState } from "react";
import { bulkApproveRoomConstraintCandidates, fetchRoomConstraintCandidates, reviewRoomConstraintCandidate } from "../api";
import RoomConstraintQueue from "../components/RoomConstraintQueue";
import LoadingState from "../components/LoadingState";
import { useToast } from "../components/Toast";
import { Alert, Button } from "../ui";
import type { ReviewStatus, RoomTypeConstraintCandidate } from "../types";

export default function RoomConstraintsPage() {
  const toast = useToast();
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
    toast(decision === "approve" ? "Room type now required for that class" : "Marked: any room is fine");
    load(reviewStatus);
  };

  const handleBulkApprove = async (ids: number[], reviewedBy: string, note?: string) => {
    const result = await bulkApproveRoomConstraintCandidates(ids, reviewedBy, note);
    toast(`${result.approved_count} room-type constraint${result.approved_count === 1 ? "" : "s"} approved`);
    load(reviewStatus);
    return result;
  };

  if (error)
    return (
      <div className="p-6">
        <Alert tone="critical" action={<Button size="sm" onClick={() => load(reviewStatus)}>Retry</Button>} onDismiss={() => setError(null)}>
          Failed to load room-constraint candidates: {error}
        </Alert>
      </div>
    );
  if (!candidates) return <LoadingState label="Loading room-constraint candidates…" />;

  return (
    <RoomConstraintQueue
      candidates={candidates}
      reviewStatus={reviewStatus}
      onReviewStatusChange={setReviewStatus}
      onReview={handleReview}
      onBulkApprove={handleBulkApprove}
    />
  );
}
