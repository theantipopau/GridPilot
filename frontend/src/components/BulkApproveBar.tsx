import { useState } from "react";

interface Props {
  count: number;
  label: string;
  reviewedBy: string;
  onConfirm: (reviewedBy: string, note?: string) => Promise<{ approved_count: number }>;
}

// The only bulk write in this app - every other review decision is one
// record at a time (docs/roadmap-v3.md 1.3). Type-to-confirm the exact
// count, deliberately more friction than a plain confirm dialog, since
// nothing else here lets one click change more than one record.
export default function BulkApproveBar({ count, label, reviewedBy, onConfirm }: Props) {
  const [open, setOpen] = useState(false);
  const [typed, setTyped] = useState("");
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  if (count === 0) return null;

  const confirmPhrase = `approve ${count}`;
  const canConfirm = typed.trim().toLowerCase() === confirmPhrase;

  const reset = () => {
    setOpen(false);
    setTyped("");
    setError(null);
  };

  const handleConfirm = async () => {
    if (!reviewedBy.trim()) {
      setError("Enter your name (above) before bulk-approving.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const r = await onConfirm(reviewedBy.trim(), `Bulk-approved: ${label}`);
      setResult(`${r.approved_count} candidate${r.approved_count === 1 ? "" : "s"} approved.`);
      reset();
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="mb-4 rounded-lg border border-emerald-200 bg-emerald-50 p-3 text-sm">
      {!open ? (
        <div className="flex items-center justify-between gap-3">
          <span className="text-emerald-900">
            <span className="font-medium">{count}</span> candidate{count === 1 ? "" : "s"} at {label} - a clean signal
            worth approving in one action instead of {count} clicks.
          </span>
          <button
            type="button"
            onClick={() => {
              setOpen(true);
              setResult(null);
            }}
            className="shrink-0 rounded-md bg-emerald-600 px-3 py-1.5 text-xs font-medium text-white transition-colors duration-150 hover:bg-emerald-700"
          >
            Approve all {label} ({count})
          </button>
        </div>
      ) : (
        <div className="flex flex-col gap-2">
          <p className="text-emerald-900">
            This will mark <span className="font-medium">{count}</span> candidate{count === 1 ? "" : "s"} `APPROVED` in
            one action, as <span className="font-medium">{reviewedBy || "(enter your name above)"}</span>. Type{" "}
            <code className="rounded bg-white px-1 py-0.5 text-xs">{confirmPhrase}</code> to confirm.
          </p>
          <div className="flex items-center gap-2">
            <input
              type="text"
              value={typed}
              onChange={(e) => setTyped(e.target.value)}
              placeholder={confirmPhrase}
              className="w-48 rounded-md border border-slate-300 px-2 py-1 text-sm"
              autoFocus
            />
            <button
              type="button"
              disabled={!canConfirm || busy}
              onClick={handleConfirm}
              className="rounded-md bg-emerald-600 px-3 py-1.5 text-xs font-medium text-white transition-colors duration-150 hover:bg-emerald-700 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {busy ? "Approving…" : "Confirm"}
            </button>
            <button
              type="button"
              onClick={reset}
              disabled={busy}
              className="rounded-md border border-slate-300 px-3 py-1.5 text-xs font-medium text-slate-600 hover:bg-white"
            >
              Cancel
            </button>
          </div>
        </div>
      )}
      {error && <p className="mt-2 text-xs text-red-700">{error}</p>}
      {result && <p className="mt-2 text-xs text-emerald-700">{result}</p>}
    </div>
  );
}
