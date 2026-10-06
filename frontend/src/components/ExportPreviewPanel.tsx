import { useState } from "react";
import { fetchExportPreview } from "../api";
import type { ExportPreview } from "../types";
import { Alert, Button, DetailSection, StatusIndicator } from "../ui";

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
    <DetailSection
      title="Export"
      description="Checks only - never writes a file. Producing the actual .tfx is deliberately a terminal command, not a button, since it's the one action that touches what Timetabling Solutions would read back in."
      actions={
        <Button size="sm" variant="secondary" loading={loading} onClick={load}>
          {loading ? "Checking…" : "Preview export"}
        </Button>
      }
      headingLevel={2}
    >
      {error && (
        <Alert tone="critical" className="mb-3" onDismiss={() => setError(null)}>
          {error}
        </Alert>
      )}

      {preview && (
        <div className="flex flex-col gap-2">
          <Alert tone={preview.ready ? "success" : "critical"}>
            {preview.ready ? "Ready to export" : "Not ready - see failing gate(s) below"}
          </Alert>
          <ul className="flex flex-col gap-1">
            {Object.entries(preview.gates).map(([name, gate]) => (
              <li
                key={name}
                className="flex items-center justify-between rounded border border-border bg-surface px-2.5 py-1.5 text-sm"
              >
                <span className="text-text-secondary">{GATE_LABELS[name] ?? name}</span>
                <StatusIndicator
                  size="sm"
                  tone={gate.passed ? "success" : "critical"}
                  label={gate.passed ? "Pass" : "Fail"}
                />
              </li>
            ))}
          </ul>
          {preview.ready && (
            <div className="rounded-lg border border-border bg-surface-sunken p-3">
              <p className="text-label">To actually generate the file, run from a terminal</p>
              <code className="text-code mt-1.5 block overflow-x-auto rounded-md border border-border bg-surface p-2">
                python -m app.export.run --change-set-id {changeSetId} --confirm
              </code>
            </div>
          )}
        </div>
      )}
    </DetailSection>
  );
}
