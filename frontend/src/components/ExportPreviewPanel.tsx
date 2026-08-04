import { useState } from "react";
import { fetchExportPreview } from "../api";
import type { ExportPreview } from "../types";

const GATE_LABELS: Record<string, string> = {
  json_round_trip: "Valid JSON",
  structural_comparison: "Structure unchanged",
  unchanged_record_fidelity: "Untouched records unchanged",
  referential_integrity: "References resolve",
  change_set_reconciliation: "Changes applied correctly",
  no_new_clashes: "No new clashes introduced",
};

export default function ExportPreviewPanel({ changeSetId }: { changeSetId: number }) {
  const [preview, setPreview] = useState<ExportPreview | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      setPreview(await fetchExportPreview(changeSetId));
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="rounded-lg border border-slate-200 bg-white p-3 text-sm">
      <div className="flex items-center justify-between">
        <h3 className="font-semibold text-slate-700">Export</h3>
        <button
          type="button"
          onClick={load}
          disabled={loading}
          className="rounded-md bg-slate-700 px-3 py-1.5 text-xs font-medium text-white disabled:opacity-50"
        >
          {loading ? "Checking…" : "Preview export"}
        </button>
      </div>
      <p className="mt-1 text-xs text-slate-500">
        Checks only - never writes a file. Producing the actual .tfx is deliberately a terminal command, not a
        button, since it's the one action that touches what Timetabling Solutions would read back in.
      </p>

      {error && <p className="mt-2 text-xs text-red-600">{error}</p>}

      {preview && (
        <div className="mt-3">
          <div className={`mb-2 rounded p-2 text-xs font-medium ${preview.ready ? "bg-emerald-50 text-emerald-800" : "bg-red-50 text-red-800"}`}>
            {preview.ready ? "Ready to export" : "Not ready - see failing gate(s) below"}
          </div>
          <div className="flex flex-col gap-1">
            {Object.entries(preview.gates).map(([name, gate]) => (
              <div key={name} className="flex items-center justify-between rounded border border-slate-100 px-2 py-1 text-xs">
                <span>{GATE_LABELS[name] ?? name}</span>
                <span className={gate.passed ? "text-emerald-700" : "text-red-700"}>
                  {gate.passed ? "Pass" : "Fail"}
                </span>
              </div>
            ))}
          </div>
          {preview.ready && (
            <div className="mt-3 rounded bg-slate-50 p-2 text-xs text-slate-600">
              <p className="mb-1">To actually generate the file, run from a terminal:</p>
              <code className="block rounded bg-slate-800 p-2 text-slate-100">
                python -m app.export.run --change-set-id {changeSetId} --confirm
              </code>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
