import { useEffect, useState } from "react";
import { fetchFindings, runMassRepair } from "../api";
import FindingsList from "../components/FindingsList";
import LoadingState from "../components/LoadingState";
import PageHeader from "../components/PageHeader";
import { IconAlertTriangle, IconWand } from "../components/icons";
import type { Finding, FindingsResponse, RepairResult, SuggestionCandidate } from "../types";

interface Props {
  onProposeFix?: (finding: Finding) => void;
  onApplySuggestion?: (finding: Finding, candidate: SuggestionCandidate) => Promise<void>;
  onOpenChangeSet?: (changeSetId: number) => void;
}

type StatusTab = "OPEN" | "ACCEPTED_RISK" | "ALL";

const TABS: { value: StatusTab; label: string }[] = [
  { value: "OPEN", label: "Open" },
  { value: "ACCEPTED_RISK", label: "Accepted risk" },
  { value: "ALL", label: "All" },
];

export default function FindingsPage({ onProposeFix, onApplySuggestion, onOpenChangeSet }: Props) {
  const [statusTab, setStatusTab] = useState<StatusTab>("OPEN");
  const [data, setData] = useState<FindingsResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [reviewedBy, setReviewedBy] = useState("");
  const [repairing, setRepairing] = useState(false);
  const [repairResult, setRepairResult] = useState<RepairResult | null>(null);
  const [repairError, setRepairError] = useState<string | null>(null);

  const load = (status: StatusTab) => {
    fetchFindings(status).then(setData).catch((e) => setError(String(e)));
  };

  useEffect(() => {
    load(statusTab);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [statusTab]);

  const handleRepair = async () => {
    if (!reviewedBy.trim()) {
      alert("Enter your name before running the repair solver.");
      return;
    }
    setRepairing(true);
    setRepairError(null);
    setRepairResult(null);
    try {
      const result = await runMassRepair(null, reviewedBy.trim());
      setRepairResult(result);
      load(statusTab);
    } catch (e) {
      setRepairError(String(e));
    } finally {
      setRepairing(false);
    }
  };

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
          <button
            type="button"
            onClick={handleRepair}
            disabled={repairing}
            className="ml-auto flex items-center gap-1.5 rounded-md bg-violet-600 px-3 py-1.5 text-sm font-medium text-white transition-colors duration-150 hover:bg-violet-700 disabled:opacity-50"
            title="Runs a constraint solver over every open double-booking, capacity, and room-type finding at once - see docs/mass-repair.md"
          >
            <IconWand className="h-4 w-4" />
            {repairing ? "Solving…" : "Repair with solver"}
          </button>
        </div>

        {repairError && (
          <div className="mb-4 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">{repairError}</div>
        )}

        {repairResult && (
          <div className="mb-4 rounded-lg border border-violet-200 bg-violet-50 p-3 text-sm">
            <div className="flex items-center justify-between">
              <span className="font-medium text-violet-900">
                {repairResult.status === "SOLVED" && "Resolved everything it could fix."}
                {repairResult.status === "PARTIAL" && "Resolved some, not all."}
                {repairResult.status === "INFEASIBLE" && "Couldn't resolve any of these without a regression."}
                {repairResult.status === "NO_MOVABLE_ENTRIES" && "Nothing here was repair-eligible."}
              </span>
              <button type="button" onClick={() => setRepairResult(null)} className="text-xs text-violet-400 hover:text-violet-700">
                Dismiss
              </button>
            </div>
            <p className="mt-1 text-xs text-violet-700">
              {repairResult.moved_count} lesson{repairResult.moved_count === 1 ? "" : "s"} moved &middot;{" "}
              {repairResult.findings_resolved.length} of{" "}
              {repairResult.findings_resolved.length + repairResult.findings_unresolved.length} eligible finding
              {repairResult.findings_resolved.length + repairResult.findings_unresolved.length === 1 ? "" : "s"} resolved
              {repairResult.not_eligible.length > 0 && ` · ${repairResult.not_eligible.length} not repair-eligible`}
              {" · "}
              {repairResult.solve_time_seconds.toFixed(1)}s
            </p>
            {repairResult.change_set_id != null && onOpenChangeSet && (
              <button
                type="button"
                onClick={() => onOpenChangeSet(repairResult.change_set_id!)}
                className="mt-2 rounded-md bg-violet-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-violet-700"
              >
                Review in Change Sets
              </button>
            )}
          </div>
        )}

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
