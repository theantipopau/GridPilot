import { useEffect, useState } from "react";
import { bulkApproveTeacherCapabilityCandidates, fetchTeacherCapabilityCandidates, reviewTeacherCapabilityCandidate } from "../api";
import TeacherCapabilityQueue from "../components/TeacherCapabilityQueue";
import LoadingState from "../components/LoadingState";
import { useToast } from "../components/Toast";
import { Alert, Button } from "../ui";
import type { CapabilityStatus, TeacherCapabilityCandidate } from "../types";

export default function TeacherCapabilitiesPage() {
  const toast = useToast();
  const [capabilityStatus, setCapabilityStatus] = useState<CapabilityStatus>("REVIEW_REQUIRED");
  const [candidates, setCandidates] = useState<TeacherCapabilityCandidate[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = (status: CapabilityStatus) => {
    fetchTeacherCapabilityCandidates(status)
      .then((r) => setCandidates(r.candidates))
      .catch((e) => setError(String(e)));
  };

  useEffect(() => {
    load(capabilityStatus);
  }, [capabilityStatus]);

  const handleReview = async (id: number, decision: "approve" | "reject", reviewedBy: string, note?: string) => {
    await reviewTeacherCapabilityCandidate(id, decision, reviewedBy, note);
    toast(decision === "approve" ? "Marked qualified" : "Marked not qualified");
    load(capabilityStatus);
  };

  const handleBulkApprove = async (ids: number[], reviewedBy: string, note?: string) => {
    const result = await bulkApproveTeacherCapabilityCandidates(ids, reviewedBy, note);
    toast(`${result.approved_count} teacher${result.approved_count === 1 ? "" : "s"} marked qualified`);
    load(capabilityStatus);
    return result;
  };

  if (error)
    return (
      <div className="p-6">
        <Alert tone="critical" action={<Button size="sm" onClick={() => load(capabilityStatus)}>Retry</Button>} onDismiss={() => setError(null)}>
          Failed to load teacher-capability candidates: {error}
        </Alert>
      </div>
    );
  if (!candidates) return <LoadingState label="Loading teacher-capability candidates…" />;

  return (
    <TeacherCapabilityQueue
      candidates={candidates}
      capabilityStatus={capabilityStatus}
      onStatusChange={setCapabilityStatus}
      onReview={handleReview}
      onBulkApprove={handleBulkApprove}
    />
  );
}
