import { useEffect, useState } from "react";
import { fetchAuditEvents, fetchChangeSets, fetchDashboard, fetchFindings } from "../api";
import CountUp from "../components/CountUp";
import { IconHome, IconUpload } from "../components/icons";
import type { Tab } from "../components/Sidebar";
import {
  Alert,
  Badge,
  Button,
  DetailSection,
  EmptyState,
  PageHeader,
  SummaryMetric,
  cx,
  toneForSeverity,
} from "../ui";
import type { AuditEvent, ChangeSetSummary, DashboardData, FindingsResponse, IngestStatus, Severity } from "../types";

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

export interface QueueCounts {
  findings: number;
  composites: number;
  roomConstraints: number;
  teacherCapabilities: number;
  teachingRequirements: number;
  changes: number;
}

interface Props {
  onNavigate: (tab: Tab) => void;
  onImportClick: () => void;
  /** Already loaded by the shell - the dashboard restates it rather than
   *  refetching, so the header and the sidebar can never disagree. */
  ingestStatus: IngestStatus;
  /** Badge counts the shell already fetched for the navigation. */
  queueCounts: QueueCounts;
}

interface AttentionRow {
  id: string;
  label: string;
  detail: string;
  count: number;
  tone: "critical" | "warning" | "info" | "accent" | "brand";
  tab: Tab;
}

function formatWhen(iso: string | null | undefined): string {
  if (!iso) return "never";
  const d = new Date(iso);
  const today = new Date();
  const sameDay = d.toDateString() === today.toDateString();
  if (sameDay) return `today at ${d.toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" })}`;
  return d.toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" });
}

/** The first screen of the app. It answers, in order: what is loaded, when,
 *  is validation healthy, what needs attention, what blocks approval, which
 *  draft is active, and what to do next - every figure computed from the
 *  loaded export, nothing simulated (docs/ui-ux-audit.md §3.1). */
export default function DashboardPage({ onNavigate, onImportClick, ingestStatus, queueCounts }: Props) {
  const [data, setData] = useState<DashboardData | null>(null);
  const [findings, setFindings] = useState<FindingsResponse | null>(null);
  const [changeSets, setChangeSets] = useState<ChangeSetSummary[] | null>(null);
  const [recentEvents, setRecentEvents] = useState<AuditEvent[]>([]);
  const [error, setError] = useState<string | null>(null);

  // Critical path: the dashboard cannot render without its own payload.
  useEffect(() => {
    fetchDashboard().then(setData).catch((e) => setError(String(e)));
  }, []);

  // Supporting detail: a failure here degrades a section, never the screen.
  useEffect(() => {
    fetchFindings("OPEN").then(setFindings).catch(() => setFindings(null));
    fetchChangeSets()
      .then((r) => setChangeSets(r.change_sets))
      .catch(() => setChangeSets(null));
    fetchAuditEvents()
      .then((r) => setRecentEvents(r.events.slice(0, 6)))
      .catch(() => setRecentEvents([]));
  }, []);

  if (error) {
    return (
      <div className="p-6">
        <PageHeader title="Dashboard" icon={<IconHome className="h-5 w-5" />} />
        <Alert tone="critical" title="Dashboard could not load" action={<Button size="sm" variant="primary" onClick={() => window.location.reload()}>Retry</Button>}>
          {error}
        </Alert>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="p-6" role="status" aria-live="polite">
        <span className="sr-only">Loading dashboard…</span>
        <div className="mb-5 h-10 w-72 max-w-full skeleton" />
        <div className="mb-5 h-14 w-full skeleton" />
        <div className="mb-5 grid grid-cols-2 gap-3 lg:grid-cols-4">
          {[0, 1, 2, 3].map((i) => (
            <div key={i} className="h-24 skeleton" style={{ animationDelay: `${i * 80}ms` }} />
          ))}
        </div>
        <div className="grid grid-cols-1 gap-5 lg:grid-cols-3">
          <div className="h-72 skeleton lg:col-span-2" />
          <div className="h-72 skeleton" />
        </div>
      </div>
    );
  }

  const openFindings =
    data.findings_by_severity.critical + data.findings_by_severity.warning + data.findings_by_severity.info;

  const pendingReviews =
    data.composites_pending + queueCounts.roomConstraints + queueCounts.teacherCapabilities + queueCounts.teachingRequirements;

  const drafts = (changeSets ?? []).filter((c) => c.approval_status === "DRAFT");
  const invalidDrafts = drafts.filter((c) => c.validation_status === "INVALID");
  const unvalidatedDrafts = drafts.filter((c) => c.validation_status === "NOT_VALIDATED");

  // Health is stated in words as well as colour: a critical finding count of
  // zero is the only "healthy" answer.
  const health =
    data.findings_by_severity.critical > 0
      ? { tone: "critical" as const, text: `${data.findings_by_severity.critical} critical findings open` }
      : openFindings > 0
        ? { tone: "warning" as const, text: `${openFindings} findings open, none critical` }
        : { tone: "success" as const, text: "No open findings" };

  const allAttention: AttentionRow[] = [
    {
      id: "critical",
      label: "Critical findings",
      detail: "Clashes and capacity breaches the rules engine flagged",
      count: data.findings_by_severity.critical,
      tone: "critical",
      tab: "findings",
    },
    {
      id: "composites",
      label: "Composite reviews pending",
      detail: "Confirm merged class groups so clash findings stop firing",
      count: data.composites_pending,
      tone: "brand",
      tab: "composites",
    },
    {
      id: "room-constraints",
      label: "Room-type constraints to confirm",
      detail: "Inferred from how each class is already scheduled",
      count: queueCounts.roomConstraints,
      tone: "brand",
      tab: "room-constraints",
    },
    {
      id: "teacher-capabilities",
      label: "Teacher capabilities to confirm",
      detail: "Blocked pending human confirmation",
      count: queueCounts.teacherCapabilities,
      tone: "brand",
      tab: "teacher-capabilities",
    },
    {
      id: "teaching-requirements",
      label: "Teaching requirements to confirm",
      detail: "Demand model awaiting review",
      count: queueCounts.teachingRequirements,
      tone: "brand",
      tab: "teaching-requirements",
    },
    {
      id: "changes",
      label: "Draft change sets awaiting decision",
      detail: "Validate, then approve or reject - the source timetable is untouched",
      count: drafts.length || data.change_sets_draft,
      tone: "accent",
      tab: "changes",
    },
  ];
  const attention = allAttention.filter((row) => row.count > 0);

  // Top rules turn 402 findings into a shape: which rule is producing them.
  const ruleGroups = (() => {
    if (!findings) return [];
    const map = new Map<string, { rule: string; count: number; severity: Severity }>();
    for (const f of findings.findings) {
      const existing = map.get(f.rule_id);
      if (existing) {
        existing.count += 1;
      } else {
        map.set(f.rule_id, { rule: f.rule_id, count: 1, severity: f.severity });
      }
    }
    return [...map.values()].sort((a, b) => b.count - a.count).slice(0, 6);
  })();

  const sourceFile = ingestStatus.last_ingest?.tfx_source_path?.split(/[\\/]/).pop()?.replace(/^\d{8}T\d{12}_/, "") ?? null;

  return (
    <div className="p-6">
      <PageHeader
        icon={<IconHome className="h-5 w-5" />}
        title="Dashboard"
        description="Every number here is computed from the timetable that is actually loaded - nothing simulated."
        actions={
          <>
            <Button size="sm" onClick={() => onNavigate("timetable")}>
              Open master grid
            </Button>
            <Button size="sm" variant="primary" iconLeft={<IconUpload className="h-4 w-4" />} onClick={onImportClick}>
              Import…
            </Button>
          </>
        }
        meta={
          <Badge tone={health.tone} variant="soft">
            {health.text}
          </Badge>
        }
      />

      {/* Source / import status strip - the "what is loaded, when" answer. */}
      <div className="mb-5 flex flex-wrap items-center gap-x-6 gap-y-2 rounded-lg border border-border bg-surface px-4 py-3">
        <div className="flex min-w-0 items-center gap-2">
          <span aria-hidden="true" className="h-2 w-2 shrink-0 rounded-full bg-success" />
          <div className="min-w-0">
            <p className="truncate text-sm font-medium text-text-primary" title={sourceFile ?? undefined}>
              {sourceFile ?? "No file loaded"}
            </p>
            <p className="text-meta">
              Imported {formatWhen(ingestStatus.last_ingest?.finished_at ?? ingestStatus.last_ingest?.started_at)}
            </p>
          </div>
        </div>
        <div>
          <p className="text-sm font-medium text-text-primary">Rules engine</p>
          <p className="text-meta">Last run {formatWhen(data.last_rules_run_at)}</p>
        </div>
        <div className="hidden sm:block">
          <p className="text-sm font-medium text-text-primary">Cycle</p>
          <p className="nums text-meta">
            {data.counts.days} days × {data.counts.periods_per_day} periods · {data.counts.lessons.toLocaleString()} lessons
          </p>
        </div>
        <div className="ml-auto flex items-center gap-2">
          <Button size="sm" onClick={() => onNavigate("audit")}>
            Audit trail
          </Button>
        </div>
      </div>

      {/* Restrained metric strip: four figures that carry decisions. */}
      <div className="mb-3 grid grid-cols-2 gap-3 lg:grid-cols-4">
        <SummaryMetric
          label="Open findings"
          value={<CountUp value={openFindings} />}
          tone={data.findings_by_severity.critical > 0 ? "critical" : openFindings > 0 ? "warning" : "success"}
          emphasis
          hint={`${data.findings_by_severity.critical} critical · ${data.findings_by_severity.warning} warning · ${data.findings_by_severity.info} info`}
          onClick={() => onNavigate("findings")}
        />
        <SummaryMetric
          label="Awaiting your review"
          value={<CountUp value={pendingReviews} />}
          tone={pendingReviews > 0 ? "warning" : "success"}
          emphasis
          hint="Composites, room types, capabilities, requirements"
          onClick={() => onNavigate("composites")}
        />
        <SummaryMetric
          label="Draft change sets"
          value={<CountUp value={drafts.length} />}
          tone="accent"
          emphasis
          hint={drafts.length === 0 ? "Nothing awaiting approval" : `${invalidDrafts.length} invalid · ${unvalidatedDrafts.length} not yet validated`}
          onClick={() => onNavigate("changes")}
        />
        <SummaryMetric
          label="Room utilisation"
          value={data.room_utilisation_pct != null ? <CountUp value={data.room_utilisation_pct} decimals={0} /> : "—"}
          suffix={data.room_utilisation_pct != null ? "%" : undefined}
          emphasis
          hint="Average across all rooms and lesson slots"
          onClick={() => onNavigate("rooms")}
        />
      </div>

      {/* Essential counts, one line - context, not decoration. */}
      <p className="mb-5 text-meta nums">
        {data.counts.teachers} teachers · {data.counts.students.toLocaleString()} students · {data.counts.rooms} rooms ·{" "}
        {data.counts.roll_classes} roll classes · {data.counts.class_names} class offerings · {data.counts.lessons.toLocaleString()}{" "}
        lessons per cycle
      </p>

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-3">
        <div className="flex min-w-0 flex-col gap-5 lg:col-span-2">
          <DetailSection
            title="Needs attention"
            description="Ordered by what blocks approval and export first"
            aside={attention.length > 0 ? `${attention.length} open` : undefined}
          >
            {attention.length === 0 ? (
              <EmptyState
                tone="positive"
                title="Nothing is waiting on you"
                description="Findings are clear and every review queue is empty. Open the master grid to inspect the timetable, or import a newer export."
                action={<Button size="sm" onClick={() => onNavigate("timetable")}>Open master grid</Button>}
              />
            ) : (
              <ul className="flex flex-col gap-1.5">
                {attention.map((row) => (
                  <li key={row.id}>
                    <button
                      type="button"
                      onClick={() => onNavigate(row.tab)}
                      className={cx(
                        "flex w-full items-center gap-3 rounded-md border border-transparent px-2.5 py-2 text-left",
                        "transition-colors duration-150 hover:border-border hover:bg-hovered",
                        "focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-focus",
                      )}
                    >
                      <span
                        aria-hidden="true"
                        className={cx(
                          "h-6 w-1 shrink-0 rounded-full",
                          row.tone === "critical" && "bg-critical",
                          row.tone === "warning" && "bg-warning",
                          row.tone === "accent" && "bg-accent",
                          row.tone === "brand" && "bg-brand",
                          row.tone === "info" && "bg-information",
                        )}
                      />
                      <span className="min-w-0 flex-1">
                        <span className="block truncate text-sm font-medium text-text-primary">{row.label}</span>
                        <span className="block truncate text-meta">{row.detail}</span>
                      </span>
                      <span className="nums shrink-0 text-lg font-semibold text-text-primary">{row.count}</span>
                      <svg viewBox="0 0 16 16" aria-hidden="true" className="h-4 w-4 shrink-0 text-text-muted" fill="none">
                        <path d="m6 4 4 4-4 4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
                      </svg>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </DetailSection>

          <DetailSection
            title="Open findings by severity and rule"
            description="Which rules are producing the work"
            actions={
              <Button size="sm" onClick={() => onNavigate("findings")}>
                Open findings
              </Button>
            }
          >
            <div className="mb-3 flex flex-wrap gap-1.5">
              {(["critical", "warning", "info"] as Severity[]).map((sev) => (
                <button
                  key={sev}
                  type="button"
                  onClick={() => onNavigate("findings")}
                  className="transition-transform duration-150 hover:scale-[1.02] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus"
                >
                  <Badge tone={toneForSeverity(sev)} variant="soft">
                    <span className="nums">{data.findings_by_severity[sev]}</span> {sev}
                  </Badge>
                </button>
              ))}
            </div>
            {ruleGroups.length === 0 ? (
              <p className="text-meta">{findings ? "No open findings." : "Finding detail unavailable right now."}</p>
            ) : (
              <ul className="flex flex-col divide-y divide-border">
                {ruleGroups.map((g) => (
                  <li key={g.rule}>
                    <button
                      type="button"
                      onClick={() => onNavigate("findings")}
                      className={cx(
                        "flex w-full items-center gap-3 px-1 py-1.5 text-left",
                        "transition-colors duration-150 hover:bg-hovered",
                        "focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-focus",
                      )}
                    >
                      <span className="text-code truncate text-text-secondary">{g.rule}</span>
                      <span className="ml-auto nums text-sm font-medium text-text-primary">{g.count}</span>
                      <Badge tone={toneForSeverity(g.severity)} size="sm" variant="outline">
                        {g.severity}
                      </Badge>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </DetailSection>
        </div>

        <div className="flex min-w-0 flex-col gap-5">
          <DetailSection
            title="Active draft change sets"
            description="Approving records a decision - it never mutates the imported source"
            actions={
              <Button size="sm" onClick={() => onNavigate("changes")}>
                Manage
              </Button>
            }
          >
            {invalidDrafts.length > 0 && (
              <Alert tone="critical" className="mb-3" title="Approval is blocked">
                {invalidDrafts.length} draft change set{invalidDrafts.length === 1 ? "" : "s"} failed validation.
              </Alert>
            )}
            {unvalidatedDrafts.length > 0 && (
              <Alert tone="warning" className="mb-3" title="Not yet validated">
                {unvalidatedDrafts.length} draft{unvalidatedDrafts.length === 1 ? "" : "s"} must be validated before approval.
              </Alert>
            )}
            {!changeSets ? (
              <p className="text-meta">Loading change sets…</p>
            ) : drafts.length === 0 ? (
              <EmptyState
                title="No draft change sets"
                description="Propose a move from the timetable, or apply a suggested fix from a finding, to start one."
                action={<Button size="sm" onClick={() => onNavigate("findings")}>Review findings</Button>}
              />
            ) : (
              <ul className="flex flex-col gap-1.5">
                {drafts.slice(0, 5).map((cs) => (
                  <li key={cs.id}>
                    <button
                      type="button"
                      onClick={() => onNavigate("changes")}
                      className={cx(
                        "flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left",
                        "transition-colors duration-150 hover:bg-hovered",
                        "focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-focus",
                      )}
                    >
                      <span className="min-w-0 flex-1">
                        <span className="block truncate text-sm font-medium text-text-primary">{cs.name}</span>
                        <span className="nums block text-meta">
                          {cs.change_count} change{cs.change_count === 1 ? "" : "s"} · created{" "}
                          {new Date(cs.created_at).toLocaleDateString(undefined, { day: "numeric", month: "short" })}
                        </span>
                      </span>
                      <Badge
                        size="sm"
                        tone={cs.validation_status === "VALID" ? "success" : cs.validation_status === "INVALID" ? "critical" : "neutral"}
                        variant="outline"
                      >
                        {cs.validation_status.replace("_", " ").toLowerCase()}
                      </Badge>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </DetailSection>

          <DetailSection
            title="Recent activity"
            actions={
              <Button size="sm" onClick={() => onNavigate("audit")}>
                Full audit
              </Button>
            }
          >
            {recentEvents.length === 0 ? (
              <p className="text-meta">No audit events yet.</p>
            ) : (
              <ul className="flex flex-col gap-2.5">
                {recentEvents.map((e) => (
                  <li key={e.id} className="min-w-0">
                    <div className="flex flex-wrap items-baseline justify-between gap-x-2">
                      <span className="truncate text-sm font-medium text-text-primary">
                        {EVENT_TYPE_LABELS[e.event_type] ?? e.event_type.replace(/_/g, " ")}
                      </span>
                      <time className="nums shrink-0 text-meta" dateTime={e.occurred_at}>
                        {new Date(e.occurred_at).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" })}
                      </time>
                    </div>
                    <p className="text-meta">{e.summary}</p>
                  </li>
                ))}
              </ul>
            )}
          </DetailSection>
        </div>
      </div>
    </div>
  );
}
