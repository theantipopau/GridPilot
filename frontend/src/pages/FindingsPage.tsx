import { useEffect, useState } from "react";
import { fetchFindings } from "../api";
import FindingsList from "../components/FindingsList";
import LoadingState from "../components/LoadingState";
import PageHeader from "../components/PageHeader";
import { IconAlertTriangle } from "../components/icons";
import type { Finding, FindingsResponse, SuggestionCandidate } from "../types";

interface Props {
  onProposeFix?: (finding: Finding) => void;
  onApplySuggestion?: (finding: Finding, candidate: SuggestionCandidate) => Promise<void>;
}

export default function FindingsPage({ onProposeFix, onApplySuggestion }: Props) {
  const [data, setData] = useState<FindingsResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchFindings().then(setData).catch((e) => setError(String(e)));
  }, []);

  if (error) return <div className="p-6 text-red-600">Failed to load findings: {error}</div>;
  if (!data) return <LoadingState label="Loading findings…" />;

  return (
    <div>
      <div className="px-6 pt-6">
        <PageHeader
          icon={<IconAlertTriangle className="h-5 w-5" />}
          title="Findings"
          description="Everything the deterministic rules engine flagged in the current timetable - double-bookings, capacity, and load issues."
        />
      </div>
      <FindingsList
        findings={data.findings}
        countsBySeverity={data.counts_by_severity}
        onProposeFix={onProposeFix}
        onApplySuggestion={onApplySuggestion}
      />
    </div>
  );
}
