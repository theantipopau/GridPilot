import { useEffect, useState } from "react";
import { fetchBlockingDemand } from "../api";
import type { BlockingDemandResponse } from "../types";

function pct(ratio: number | null): string {
  return ratio == null ? "—" : `${Math.round(ratio * 100)}%`;
}

// roadmap-v3.md 4.1 Phase 1 - structural analysis of the .sfx
// subject-selection export (which subjects can never be combined, which
// lines carry the tightest demand, which classes are running well under
// their stated cap), computed with zero new data and no solver. A
// collapsible panel, not its own sidebar tab, since this reads as a
// second lens on the same "blocking" concept the page already shows -
// same pattern as SolverRunHistory on the Findings page.
export default function BlockingDemand() {
  const [open, setOpen] = useState(false);
  const [data, setData] = useState<BlockingDemandResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open || data) return;
    fetchBlockingDemand()
      .then(setData)
      .catch((e) => setError(String(e)));
  }, [open, data]);

  return (
    <div className="rounded-lg border border-slate-200 bg-white">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center justify-between gap-4 px-4 py-3 text-left"
      >
        <div>
          <h2 className="text-sm font-semibold text-slate-800">Subject-selection demand</h2>
          <p className="mt-0.5 text-xs text-ink-muted">
            What the .sfx export reveals structurally, from real enrolment and the school's own
            stated class caps - not a judgement, a read.
          </p>
        </div>
        <span className="shrink-0 text-xs font-medium text-sky-700">{open ? "Hide" : "Show"}</span>
      </button>

      {open && (
        <div className="border-t border-slate-100 p-4">
          {error && <p className="text-sm text-red-600">Failed to load: {error}</p>}
          {!error && !data && <p className="text-sm text-ink-muted">Loading…</p>}

          {data && (
            <div className="flex flex-col gap-8">
              <section>
                <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">
                  Tightest demand — {data.lines.length} line{data.lines.length === 1 ? "" : "s"} with
                  enrolled electives, real enrolment against stated capacity
                </h3>
                <div className="max-h-72 overflow-y-auto rounded-md border border-slate-200">
                  <table className="w-full border-collapse text-sm">
                    <thead className="sticky top-0 bg-slate-50">
                      <tr>
                        <th className="border-b border-slate-200 p-2 text-left text-xs font-medium text-slate-500">Line</th>
                        <th className="border-b border-slate-200 p-2 text-right text-xs font-medium text-slate-500">Classes</th>
                        <th className="border-b border-slate-200 p-2 text-right text-xs font-medium text-slate-500">Enrolled / capacity</th>
                        <th className="border-b border-slate-200 p-2 text-right text-xs font-medium text-slate-500">Pressure</th>
                      </tr>
                    </thead>
                    <tbody>
                      {data.lines.map((l) => (
                        <tr key={l.sfx_line_id}>
                          <td className="border-b border-slate-100 p-2 text-slate-700">
                            {l.line_name ?? l.line_code ?? `Line ${l.sfx_line_id}`}
                          </td>
                          <td className="border-b border-slate-100 p-2 text-right text-slate-500">{l.class_count}</td>
                          <td className="border-b border-slate-100 p-2 text-right text-slate-500">
                            {l.total_enrolled} / {l.total_capacity}
                          </td>
                          <td className="border-b border-slate-100 p-2 text-right font-medium text-slate-800">
                            {pct(l.pressure)}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </section>

              <section>
                <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">
                  Under-subscribed classes — {data.under_subscribed_classes.length} running below half
                  their stated cap
                </h3>
                {data.under_subscribed_classes.length === 0 ? (
                  <p className="text-sm text-ink-muted">None - every elective class is at least half full.</p>
                ) : (
                  <div className="max-h-72 overflow-y-auto rounded-md border border-slate-200">
                    <table className="w-full border-collapse text-sm">
                      <thead className="sticky top-0 bg-slate-50">
                        <tr>
                          <th className="border-b border-slate-200 p-2 text-left text-xs font-medium text-slate-500">Class</th>
                          <th className="border-b border-slate-200 p-2 text-left text-xs font-medium text-slate-500">Roll class</th>
                          <th className="border-b border-slate-200 p-2 text-left text-xs font-medium text-slate-500">Line</th>
                          <th className="border-b border-slate-200 p-2 text-right text-xs font-medium text-slate-500">Enrolled / cap</th>
                        </tr>
                      </thead>
                      <tbody>
                        {data.under_subscribed_classes.map((c) => (
                          <tr key={c.class_code}>
                            <td className="border-b border-slate-100 p-2 font-medium text-slate-800">{c.class_code}</td>
                            <td className="border-b border-slate-100 p-2 text-slate-500">{c.roll_class_code ?? "—"}</td>
                            <td className="border-b border-slate-100 p-2 text-slate-500">{c.line_code ?? "—"}</td>
                            <td className="border-b border-slate-100 p-2 text-right text-slate-500">
                              {c.enrolled} / {c.max_class_size}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </section>

              <section>
                <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">
                  Subject pairs that can never both be taken — {data.impossible_subject_pairs.length} line
                  {data.impossible_subject_pairs.length === 1 ? "" : "s"} where two or more subjects are
                  each confined to that one line
                </h3>
                {data.impossible_subject_pairs.length === 0 ? (
                  <p className="text-sm text-ink-muted">None found.</p>
                ) : (
                  <div className="flex flex-col gap-2">
                    {data.impossible_subject_pairs.map((g) => (
                      <div key={g.sfx_line_id} className="rounded-md border border-slate-200 p-2.5 text-sm">
                        <span className="mr-2 font-medium text-slate-700">
                          {g.line_name ?? g.line_code ?? `Line ${g.sfx_line_id}`}
                        </span>
                        <span className="text-slate-500">{g.subjects.join(", ")}</span>
                      </div>
                    ))}
                  </div>
                )}
              </section>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
