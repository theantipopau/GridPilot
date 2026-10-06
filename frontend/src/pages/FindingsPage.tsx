import { useEffect, useState } from "react";
import { fetchFindings, runMassRepair } from "../api";
import FindingsList from "../components/FindingsList";
import LoadingState from "../components/LoadingState";
import { ReviewShell, ReviewerField } from "../components/ReviewShell";
import { useReviewerGate } from "../lib/reviewer";
import SolverRunHistory from "../components/SolverRunHistory";
import { Alert, Badge, Button } from "../ui";
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
  const reviewer = useReviewerGate();
  const [statusTab, setStatusTab] = useState<StatusTab>("OPEN");
  const [data, setData] = useState<FindingsResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [repairing, setRepairing] = useState(false);
  const [repairResult, setRepairResult] = useState<RepairResult | null>(null);
  const [repairError, setRepairError] = useState<string | null>(null);
  const [runHistoryKey, setRunHistoryKey] = useState(0);

  const load = (status: StatusTab) => {
    fetchFindings(status).then(setData).catch((e) => setError(String(e)));
  };

  useEffect(() => {
    load(statusTab);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [statusTab]);

  const handleRepair = async () => {
    if (!reviewer.check()) return;
    setRepairing(true);
    setRepairError(null);
    setRepairResult(null);
    try {
      const result = await runMassRepair(null, reviewer.reviewer);
      setRepairResult(result);
      setRunHistoryKey((k) => k + 1);
      load(statusTab);
    } catch (e) {
      setRepairError(String(e));
    } finally {
      setRepairing(false);
    }
  };

  if (error) {
    return (
      <div className="p-6">
        <Alert tone="critical" title="Findings failed to load" action={<Button size="sm" onClick={() => load(statusTab)}>Retry</Button>}>
          {error}
        </Alert>
      </div>
    );
  }
  if (!data) return <LoadingState label="Loading findings…" />;

  return (
    <ReviewShell
      icon={<IconAlertTriangle className="h-5 w-5" />}
      title="Findings"
      description="Everything the deterministic rules engine flagged in the current timetable - double-bookings, capacity, and load issues. Nothing here has been changed for you."
      panelId="findings-panel"
      tabs={TABS.map((t) => ({ id: t.value, label: t.label }))}
      tabValue={statusTab}
      onTabChange={setStatusTab}
      meta={
        <>
          <Badge tone="critical" size="sm">
            <span className="nums">{data.counts_by_severity.critical}</span> critical
          </Badge>
          <Badge tone="warning" size="sm">
            <span className="nums">{data.counts_by_severity.warning}</span> warning
          </Badge>
          <Badge tone="info" size="sm">
            <span className="nums">{data.counts_by_severity.info}</span> info
          </Badge>
        </>
      }
      actions={
        <>
          <ReviewerField error={reviewer.error} />
          <Button
            variant="accent"
            iconLeft={<IconWand className="h-4 w-4" />}
            loading={repairing}
            onClick={handleRepair}
            title="Runs a constraint solver over every open double-booking, capacity, and room-type finding at once - see docs/mass-repair.md"
          >
            {repairing ? "Solving…" : "Repair with solver"}
          </Button>
        </>
      }
    >
      {repairError && (
        <Alert tone="critical" className="mb-3" onDismiss={() => setRepairError(null)}>
          {repairError}
        </Alert>
      )}

      {repairResult && (
        <Alert
          tone={repairResult.status === "SOLVED" ? "success" : repairResult.status === "INFEASIBLE" ? "warning" : "info"}
          className="mb-3"
          title={
            repairResult.status === "SOLVED"
              ? "Resolved everything it could fix."
              : repairResult.status === "PARTIAL"
                ? "Resolved some, not all."
                : repairResult.status === "INFEASIBLE"
                  ? "Couldn't resolve any of these without a regression."
                  : "Nothing here was repair-eligible."
          }
          onDismiss={() => setRepairResult(null)}
          action={
            repairResult.change_set_id != null && onOpenChangeSet ? (
              <Button size="sm" variant="primary" onClick={() => onOpenChangeSet(repairResult.change_set_id!)}>
                Review in Change Sets
              </Button>
            ) : undefined
          }
        >
          <p className="nums">
            {repairResult.moved_count} lesson{repairResult.moved_count === 1 ? "" : "s"} moved ·{" "}
            {repairResult.findings_resolved.length} of{" "}
            {repairResult.findings_resolved.length + repairResult.findings_unresolved.length} eligible finding
            {repairResult.findings_resolved.length + repairResult.findings_unresolved.length === 1 ? "" : "s"} resolved
            {repairResult.not_eligible.length > 0 && ` · ${repairResult.not_eligible.length} not repair-eligible`}
            {" · "}
            {repairResult.solve_time_seconds.toFixed(1)}s
          </p>
          <p className="mt-1">
            Moves are recorded in a draft change set - the imported timetable is unchanged until you approve it.
          </p>
        </Alert>
      )}

      <SolverRunHistory refreshKey={runHistoryKey} onOpenChangeSet={onOpenChangeSet} />

      <FindingsList
        findings={data.findings}
        countsBySeverity={data.counts_by_severity}
        onProposeFix={onProposeFix}
        onApplySuggestion={onApplySuggestion}
        onReviewed={() => load(statusTab)}
      />
    </ReviewShell>
  );
}
