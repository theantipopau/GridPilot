import { Fragment, useEffect, useState } from "react";
import { explainInfeasibility, fetchSolverRuns } from "../api";
import type { RepairStatus, SolverRunSummary } from "../types";

interface Props {
  refreshKey: number;
  onOpenChangeSet?: (changeSetId: number) => void;
}

type ExplanationState =
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "done"; text: string };

const STATUS_LABEL: Record<RepairStatus, string> = {
  SOLVED: "Solved",
  PARTIAL: "Partial",
  INFEASIBLE: "Infeasible",
  NO_MOVABLE_ENTRIES: "Nothing eligible",
};

const STATUS_DOT: Record<RepairStatus, string> = {
  SOLVED: "bg-emerald-500",
  PARTIAL: "bg-amber-500",
  INFEASIBLE: "bg-red-500",
  NO_MOVABLE_ENTRIES: "bg-slate-300",
};

function formatTime(iso: string): string {
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
  }
}

// docs/roadmap-v3.md 4.2: "a solver run must be a first-class,
// persisted, comparable object, not a fire-and-forget button." This is
// the comparison surface - "Run 3 fixed 18 findings with 22 moves; Run 4
// fixed 20 with 61" as the actual interface, not a sentence someone has
// to remember from a dismissed toast.
export default function SolverRunHistory({ refreshKey, onOpenChangeSet }: Props) {
  const [open, setOpen] = useState(false);
  const [runs, setRuns] = useState<SolverRunSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<number[]>([]);
  const [explanations, setExplanations] = useState<Record<number, ExplanationState>>({});

  useEffect(() => {
    if (!open) return;
    fetchSolverRuns(20)
      .then((r) => setRuns(r.runs))
      .catch((e) => setError(String(e)));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, refreshKey]);

  const toggleSelect = (id: number) => {
    setSelected((prev) => {
      if (prev.includes(id)) return prev.filter((x) => x !== id);
      if (prev.length >= 2) return [prev[1], id];
      return [...prev, id];
    });
  };

  const compareRuns = runs?.filter((r) => selected.includes(r.id)) ?? [];

  const toggleExplanation = async (runId: number) => {
    if (explanations[runId]) {
      setExplanations((prev) => {
        const next = { ...prev };
        delete next[runId];
        return next;
      });
      return;
    }
    setExplanations((prev) => ({ ...prev, [runId]: { status: "loading" } }));
    try {
      const result = await explainInfeasibility(runId);
      setExplanations((prev) => ({ ...prev, [runId]: { status: "done", text: result.explanation } }));
    } catch (e) {
      setExplanations((prev) => ({ ...prev, [runId]: { status: "error", message: String(e) } }));
    }
  };

  return (
    <div className="mb-4">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="text-xs font-medium text-ink-muted underline hover:text-slate-600"
      >
        {open ? "Hide" : "Show"} solver run history
      </button>

      {open && (
        <div className="mt-2 rounded-lg border border-slate-200 bg-white p-3 text-sm shadow-sm">
          {error && <p className="text-xs text-red-600">{error}</p>}
          {!runs && !error && <p className="text-xs text-ink-muted">Loading…</p>}
          {runs && runs.length === 0 && (
            <p className="text-xs text-ink-muted">No solver runs yet - click "Repair with solver" above to start one.</p>
          )}

          {runs && runs.length > 0 && (
            <>
              {compareRuns.length === 2 && (
                <div className="mb-3 grid grid-cols-2 gap-3 rounded-md border border-violet-200 bg-violet-50 p-2 text-xs">
                  {compareRuns.map((r) => (
                    <div key={r.id}>
                      <div className="font-medium text-violet-900">Run {r.id}</div>
                      <div className="text-violet-700">
                        {STATUS_LABEL[r.status]} · {r.findings_resolved_count} of {r.scope_count} resolved ·{" "}
                        {r.moved_count} move{r.moved_count === 1 ? "" : "s"} · {r.solve_time_seconds.toFixed(1)}s
                      </div>
                    </div>
                  ))}
                </div>
              )}
              <table className="w-full border-collapse text-xs">
                <thead>
                  <tr className="border-b border-slate-200 text-left text-ink-muted">
                    <th className="w-6 p-1.5"></th>
                    <th className="p-1.5">Run</th>
                    <th className="p-1.5">When</th>
                    <th className="p-1.5">By</th>
                    <th className="p-1.5">Status</th>
                    <th className="p-1.5">Resolved</th>
                    <th className="p-1.5">Moves</th>
                    <th className="p-1.5">Time</th>
                    <th className="p-1.5"></th>
                  </tr>
                </thead>
                <tbody>
                  {runs.map((r) => (
                    <Fragment key={r.id}>
                      <tr className="border-b border-slate-100 last:border-0 hover:bg-slate-50">
                        <td className="p-1.5">
                          <input
                            type="checkbox"
                            checked={selected.includes(r.id)}
                            onChange={() => toggleSelect(r.id)}
                            title="Select to compare (up to 2)"
                          />
                        </td>
                        <td className="p-1.5 font-medium text-slate-700">#{r.id}</td>
                        <td className="p-1.5 text-ink-muted">{formatTime(r.created_at)}</td>
                        <td className="p-1.5 text-ink-muted">{r.created_by}</td>
                        <td className="p-1.5">
                          <span className="inline-flex items-center gap-1.5">
                            <span className={`h-1.5 w-1.5 rounded-full ${STATUS_DOT[r.status]}`} />
                            {STATUS_LABEL[r.status]}
                          </span>
                        </td>
                        <td className="p-1.5 tabular-figures text-slate-600">
                          {r.findings_resolved_count} of {r.scope_count}
                        </td>
                        <td className="p-1.5 tabular-figures text-slate-600">{r.moved_count}</td>
                        <td className="p-1.5 tabular-figures text-ink-muted">{r.solve_time_seconds.toFixed(1)}s</td>
                        <td className="p-1.5">
                          <div className="flex items-center gap-2">
                            {r.change_set_id != null && onOpenChangeSet && (
                              <button
                                type="button"
                                onClick={() => onOpenChangeSet(r.change_set_id!)}
                                className="text-violet-600 underline hover:text-violet-800"
                              >
                                View change set
                              </button>
                            )}
                            {r.findings_unresolved_count > 0 && (
                              <button
                                type="button"
                                onClick={() => toggleExplanation(r.id)}
                                title="Ask the local AI advisor why these findings couldn't be resolved - docs/roadmap-v3.md 4.3"
                                className="text-slate-500 underline hover:text-slate-700"
                              >
                                {explanations[r.id] ? "Hide explanation" : "Explain"}
                              </button>
                            )}
                          </div>
                        </td>
                      </tr>
                      {explanations[r.id] && (
                        <tr className="border-b border-slate-100 last:border-0">
                          <td colSpan={9} className="bg-slate-50 p-2.5">
                            {explanations[r.id].status === "loading" && (
                              <p className="text-xs text-ink-muted">Asking the local AI advisor…</p>
                            )}
                            {explanations[r.id].status === "error" && (
                              <p className="rounded border border-red-200 bg-red-50 p-2 text-xs text-red-700">
                                {(explanations[r.id] as { status: "error"; message: string }).message}
                              </p>
                            )}
                            {explanations[r.id].status === "done" && (
                              <p className="rounded border border-slate-200 bg-white p-2 text-xs text-slate-700">
                                {(explanations[r.id] as { status: "done"; text: string }).text}
                              </p>
                            )}
                          </td>
                        </tr>
                      )}
                    </Fragment>
                  ))}
                </tbody>
              </table>
            </>
          )}
        </div>
      )}
    </div>
  );
}
