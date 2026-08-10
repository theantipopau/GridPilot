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

type StatusTab = "OPEN" | "ACCEPTED_RISK" | "ALL";

const TABS: { value: StatusTab; label: string }[] = [
  { value: "OPEN", label: "Open" },
  { value: "ACCEPTED_RISK", label: "Accepted risk" },
  { value: "ALL", label: "All" },
];

export default function FindingsPage({ onProposeFix, onApplySuggestion }: Props) {
  const [statusTab, setStatusTab] = useState<StatusTab>("OPEN");
  const [data, setData] = useState<FindingsResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [reviewedBy, setReviewedBy] = useState("");

  const load = (status: StatusTab) => {
    fetchFindings(status).then(setData).catch((e) => setError(String(e)));
  };

  useEffect(() => {
    load(statusTab);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [statusTab]);

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
          {TABS.map((t) => (
            <button
              key={t.value}
              type="button"
              onClick={() => setStatusTab(t.value)}
              className={`px-3 py-2 text-sm font-medium ${
                statusTab === t.value
                  ? "border-b-2 border-sky-600 text-sky-700"
                  : "text-slate-500 hover:text-slate-700"
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>
      </div>
      <FindingsList
        findings={data.findings}
        countsBySeverity={data.counts_by_severity}
        reviewedBy={reviewedBy}
        onProposeFix={onProposeFix}
        onApplySuggestion={onApplySuggestion}
        onReviewed={() => load(statusTab)}
      />
    </div>
  );
}
