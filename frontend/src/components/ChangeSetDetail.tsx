import { useState } from "react";
import type { ChangeSetDetail as ChangeSetDetailType, ReferenceData } from "../types";
import AddChangeForm from "./AddChangeForm";
import ExportPreviewPanel from "./ExportPreviewPanel";

interface Prefill {
  day_code?: string;
  period_code?: string;
  teacher_code?: string;
  room_code?: string;
  class_code?: string;
  finding_id?: number;
}

export interface AddChangeParams {
  timetable_entry_id: number;
  after_day_code?: string;
  after_period_code?: string;
  after_room_code?: string;
  after_teacher_code?: string;
  reason?: string;
  finding_ids?: number[];
}

interface Props {
  changeSet: ChangeSetDetailType;
  reference: ReferenceData;
  prefill?: Prefill;
  onAddChange: (params: AddChangeParams) => Promise<void>;
  onRemoveChange: (changeId: number) => Promise<void>;
  onValidate: () => Promise<void>;
  onApprove: (reviewedBy: string) => Promise<void>;
  onReject: (reviewedBy: string) => Promise<void>;
}

const STATUS_COLORS: Record<string, string> = {
  DRAFT: "bg-slate-200 text-slate-700",
  APPROVED: "bg-emerald-600 text-white",
  REJECTED: "bg-slate-400 text-white",
  VALID: "bg-emerald-100 text-emerald-800",
  INVALID: "bg-red-100 text-red-800",
  NOT_VALIDATED: "bg-slate-100 text-slate-500",
};

export default function ChangeSetDetail({
  changeSet, reference, prefill, onAddChange, onRemoveChange, onValidate, onApprove, onReject,
}: Props) {
  const [reviewerName, setReviewerName] = useState("");
  const [busy, setBusy] = useState(false);

  const run = async (fn: () => Promise<void>) => {
    setBusy(true);
    try {
      await fn();
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-start justify-between">
        <div>
          <h2 className="text-lg font-semibold text-slate-900">{changeSet.name}</h2>
          {changeSet.description && <p className="text-sm text-slate-500">{changeSet.description}</p>}
        </div>
        <div className="flex gap-2">
          <span className={`rounded-full px-2 py-1 text-xs font-medium ${STATUS_COLORS[changeSet.validation_status]}`}>
            {changeSet.validation_status}
          </span>
          <span className={`rounded-full px-2 py-1 text-xs font-medium ${STATUS_COLORS[changeSet.approval_status]}`}>
            {changeSet.approval_status}
          </span>
        </div>
      </div>

      <div className="rounded-lg border border-slate-200 bg-white p-3">
        <h3 className="mb-2 text-sm font-semibold text-slate-700">Proposed changes ({changeSet.changes.length})</h3>
        {changeSet.changes.length === 0 ? (
          <p className="text-xs text-slate-400">No changes yet - add one below.</p>
        ) : (
          <div className="flex flex-col gap-2">
            {changeSet.changes.map((c) => (
              <div key={c.id} className="flex items-center justify-between rounded border border-slate-200 p-2 text-xs">
                <div>
                  <span className="font-medium">
                    {c.before.day_code} {c.before.period_code} / {c.before.room_code ?? "-"} / {c.before.teacher_code ?? "-"}
                  </span>
                  <span className="mx-2 text-slate-400">to</span>
                  <span className="font-medium text-sky-700">
                    {c.after.day_code} {c.after.period_code} / {c.after.room_code ?? "-"} / {c.after.teacher_code ?? "-"}
                  </span>
                  {c.reason && <div className="mt-1 text-slate-500">{c.reason}</div>}
                  {c.finding_ids.length > 0 && (
                    <div className="mt-1 text-slate-400">addresses finding(s): {c.finding_ids.join(", ")}</div>
                  )}
                </div>
                {changeSet.approval_status === "DRAFT" && (
                  <button
                    type="button"
                    onClick={() => run(() => onRemoveChange(c.id))}
                    disabled={busy}
                    className="rounded bg-slate-100 px-2 py-1 text-slate-600 hover:bg-slate-200"
                  >
                    Remove
                  </button>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {changeSet.approval_status === "DRAFT" && (
        <AddChangeForm reference={reference} prefill={prefill} onSubmit={onAddChange} />
      )}

      {changeSet.validation_result && (
        <div className="rounded-lg border border-slate-200 bg-white p-3 text-sm">
          <h3 className="mb-2 font-semibold text-slate-700">
            Validation result{changeSet.validation_result.reason ? ` - ${changeSet.validation_result.reason}` : ""}
          </h3>
          {changeSet.validation_result.resolved_findings.length > 0 && (
            <div className="mb-2">
              <p className="text-xs font-medium text-emerald-700">Resolves:</p>
              <ul className="ml-4 list-disc text-xs text-emerald-700">
                {changeSet.validation_result.resolved_findings.map((f, i) => <li key={i}>{f.title}</li>)}
              </ul>
            </div>
          )}
          {changeSet.validation_result.introduced_findings.length > 0 && (
            <div>
              <p className="text-xs font-medium text-red-700">Introduces new findings:</p>
              <ul className="ml-4 list-disc text-xs text-red-700">
                {changeSet.validation_result.introduced_findings.map((f, i) => <li key={i}>{f.title}</li>)}
              </ul>
            </div>
          )}
        </div>
      )}

      {changeSet.approval_status === "DRAFT" && (
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => run(onValidate)}
            disabled={busy || changeSet.changes.length === 0}
            className="rounded-md bg-slate-700 px-3 py-1.5 text-sm font-medium text-white disabled:opacity-50"
          >
            Validate
          </button>
          <input
            placeholder="Your name"
            value={reviewerName}
            onChange={(e) => setReviewerName(e.target.value)}
            className="rounded border border-slate-300 px-2 py-1 text-sm"
          />
          <button
            type="button"
            onClick={() => reviewerName.trim() && run(() => onApprove(reviewerName.trim()))}
            disabled={busy || changeSet.validation_status !== "VALID"}
            className="rounded-md bg-emerald-600 px-3 py-1.5 text-sm font-medium text-white disabled:opacity-50"
          >
            Approve
          </button>
          <button
            type="button"
            onClick={() => reviewerName.trim() && run(() => onReject(reviewerName.trim()))}
            disabled={busy}
            className="rounded-md bg-slate-200 px-3 py-1.5 text-sm font-medium text-slate-700 disabled:opacity-50"
          >
            Reject
          </button>
        </div>
      )}

      {changeSet.approval_status === "APPROVED" && (
        <>
          <p className="rounded-lg border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-800">
            Approved by {changeSet.reviewed_by} on {changeSet.reviewed_at}. The source timetable is unchanged - this
            record is the durable approval.
          </p>
          <ExportPreviewPanel changeSetId={changeSet.id} />
        </>
      )}
    </div>
  );
}
