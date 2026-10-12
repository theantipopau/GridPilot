import { useEffect, useState } from "react";
import { fetchAuditEvents } from "../api";
import LoadingState from "../components/LoadingState";
import { IconClipboardList, IconInbox } from "../components/icons";
import { Alert, Button, EmptyState, PageHeader } from "../ui";
import type { AuditEvent } from "../types";

const EVENT_TYPE_LABELS: Record<string, string> = {
  ingest_completed: "Data import",
  rules_run_completed: "Rules engine run",
  composite_group_reviewed: "Composite class reviewed",
  change_set_approved: "Change set approved",
  change_set_rejected: "Change set rejected",
  reingest_state_carried_forward: "Re-ingest carried forward review state",
  composite_review_dropped_on_reingest: "Composite review dropped on re-ingest",
  proposed_change_dropped_on_reingest: "Proposed change dropped on re-ingest",
};

export default function AuditPage() {
  const [events, setEvents] = useState<AuditEvent[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [expandedId, setExpandedId] = useState<number | null>(null);

  const load = () => {
    fetchAuditEvents().then((r) => setEvents(r.events)).catch((e) => setError(String(e)));
  };

  useEffect(load, []);

  if (error) {
    return (
      <div className="p-6">
        <Alert tone="critical" action={<Button size="sm" onClick={load}>Retry</Button>} onDismiss={() => setError(null)}>
          Failed to load audit trail: {error}
        </Alert>
      </div>
    );
  }
  if (!events) return <LoadingState label="Loading audit trail…" />;

  return (
    <div className="p-6">
      <PageHeader
        icon={<IconClipboardList className="h-5 w-5" />}
        title="Audit"
        description={
          'Append-only record of imports, rules-engine runs, composite-class reviews, and change-set ' +
          'approvals/rejections. This is a single-user local tool - "actor" is a free-text name entered at the ' +
          "time, not an authenticated identity."
        }
        meta={<span className="nums text-meta">{events.length} events</span>}
      />
      {events.length === 0 ? (
        <EmptyState icon={<IconInbox className="h-8 w-8" />} title="No audit events yet" />
      ) : (
        <ol className="flex flex-col gap-1.5">
          {events.map((e) => (
            <li
              key={e.id}
              className="rounded-lg border border-border bg-surface p-3 transition-colors duration-150 hover:border-border-strong"
            >
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="min-w-0">
                  <span className="text-sm font-medium text-text-primary">
                    {EVENT_TYPE_LABELS[e.event_type] ?? e.event_type}
                  </span>
                  <span className="ml-2 text-sm text-text-secondary">{e.summary}</span>
                </div>
                <div className="flex items-center gap-3 text-meta">
                  <span className="text-code">{e.actor}</span>
                  <span className="nums">{e.occurred_at}</span>
                  {e.detail && (
                    <Button
                      size="sm"
                      variant="ghost"
                      aria-expanded={expandedId === e.id}
                      onClick={() => setExpandedId(expandedId === e.id ? null : e.id)}
                    >
                      {expandedId === e.id ? "Hide detail" : "Detail"}
                    </Button>
                  )}
                </div>
              </div>
              {expandedId === e.id && e.detail && (
                <pre className="text-code mt-2 overflow-x-auto rounded-md border border-border bg-surface-sunken p-2.5">
                  {JSON.stringify(e.detail, null, 2)}
                </pre>
              )}
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}
