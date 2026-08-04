import { useEffect, useState } from "react";
import { fetchAuditEvents } from "../api";
import type { AuditEvent } from "../types";

const EVENT_TYPE_LABELS: Record<string, string> = {
  ingest_completed: "Data import",
  rules_run_completed: "Rules engine run",
  composite_group_reviewed: "Composite class reviewed",
  change_set_approved: "Change set approved",
  change_set_rejected: "Change set rejected",
};

export default function AuditPage() {
  const [events, setEvents] = useState<AuditEvent[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [expandedId, setExpandedId] = useState<number | null>(null);

  useEffect(() => {
    fetchAuditEvents().then((r) => setEvents(r.events)).catch((e) => setError(String(e)));
  }, []);

  if (error) return <div className="p-6 text-red-600">Failed to load audit trail: {error}</div>;
  if (!events) return <div className="p-6 text-slate-500">Loading…</div>;

  return (
    <div className="p-6">
      <p className="mb-4 max-w-2xl text-sm text-slate-600">
        Append-only record of imports, rules-engine runs, composite-class reviews, and change-set
        approvals/rejections. This is a single-user local tool - "actor" is a free-text name entered at the
        time, not an authenticated identity.
      </p>
      {events.length === 0 ? (
        <p className="text-sm text-slate-400">No audit events yet.</p>
      ) : (
        <div className="flex flex-col gap-1">
          {events.map((e) => (
            <div key={e.id} className="rounded-lg border border-slate-200 bg-white p-2 text-sm">
              <div className="flex items-center justify-between">
                <div>
                  <span className="font-medium text-slate-800">{EVENT_TYPE_LABELS[e.event_type] ?? e.event_type}</span>
                  <span className="ml-2 text-slate-500">{e.summary}</span>
                </div>
                <div className="flex items-center gap-3 text-xs text-slate-400">
                  <span>{e.actor}</span>
                  <span>{e.occurred_at}</span>
                  {e.detail && (
                    <button
                      type="button"
                      onClick={() => setExpandedId(expandedId === e.id ? null : e.id)}
                      className="rounded bg-slate-100 px-2 py-0.5 hover:bg-slate-200"
                    >
                      {expandedId === e.id ? "Hide detail" : "Detail"}
                    </button>
                  )}
                </div>
              </div>
              {expandedId === e.id && e.detail && (
                <pre className="mt-2 overflow-x-auto rounded bg-slate-50 p-2 text-xs text-slate-600">
                  {JSON.stringify(e.detail, null, 2)}
                </pre>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
