import { useEffect, useState } from "react";
import { fetchTeacherCapabilityCandidates, reviewTeacherCapabilityCandidate } from "../api";
import TeacherCapabilityQueue from "../components/TeacherCapabilityQueue";
import LoadingState from "../components/LoadingState";
import type { CapabilityStatus, TeacherCapabilityCandidate } from "../types";

export default function TeacherCapabilitiesPage() {
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
    load(capabilityStatus);
  };

  if (error) return <div className="p-6 text-red-600">Failed to load teacher-capability candidates: {error}</div>;
  if (!candidates) return <LoadingState label="Loading teacher-capability candidates…" />;

  return (
    <TeacherCapabilityQueue
      candidates={candidates}
      capabilityStatus={capabilityStatus}
      onStatusChange={setCapabilityStatus}
      onReview={handleReview}
    />
  );
}
