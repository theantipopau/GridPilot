import { useEffect, useState, type ReactNode } from "react";
import { fetchAuditEvents, fetchDashboard } from "../api";
import LoadingState from "../components/LoadingState";
import PageHeader from "../components/PageHeader";
import Ring from "../components/Ring";
import {
  IconAlertTriangle,
  IconCalendar,
  IconDoor,
  IconGitBranch,
  IconHome,
  IconLayers,
  IconUpload,
  IconUsers,
} from "../components/icons";
import type { AuditEvent, DashboardData } from "../types";

const EVENT_TYPE_LABELS: Record<string, string> = {
  ingest_completed: "Data import",
  rules_run_completed: "Rules engine run",
  composite_group_reviewed: "Composite class reviewed",
  change_set_approved: "Change set approved",
  change_set_rejected: "Change set rejected",
  reingest_state_carried_forward: "Re-ingest carried forward review state",
};

interface Props {
  onNavigate: (tab: "findings" | "composites" | "changes") => void;
  onImportClick: () => void;
}

export default function DashboardPage({ onNavigate, onImportClick }: Props) {
  const [data, setData] = useState<DashboardData | null>(null);
  const [recentEvents, setRecentEvents] = useState<AuditEvent[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchDashboard().then(setData).catch((e) => setError(String(e)));
    fetchAuditEvents()
      .then((r) => setRecentEvents(r.events.slice(0, 5)))
      .catch(() => {
        // Recent activity is a convenience panel - a failure here shouldn't block the dashboard.
      });
  }, []);

  if (error) return <div className="p-6 text-red-600">Failed to load dashboard: {error}</div>;
  if (!data) return <LoadingState label="Loading dashboard…" />;

  const openFindings = data.findings_by_severity.critical + data.findings_by_severity.warning + data.findings_by_severity.info;

  return (
    <div className="p-6">
      <PageHeader
        icon={<IconHome className="h-5 w-5" />}
        title="Dashboard"
        description="A live summary of the current timetable - every number here is computed from what's actually loaded, nothing simulated."
      />

      <div className="mb-6 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <ScoreCard
          label="Open findings"
          value={openFindings}
          icon={<IconAlertTriangle className="h-5 w-5" />}
          tone={data.findings_by_severity.critical > 0 ? "critical" : openFindings > 0 ? "warning" : "positive"}
          detail={`${data.findings_by_severity.critical} critical · ${data.findings_by_severity.warning} warning · ${data.findings_by_severity.info} info`}
          onClick={() => onNavigate("findings")}
        />
        <ScoreCard
          label="Composite reviews pending"
          value={data.composites_pending}
          icon={<IconLayers className="h-5 w-5" />}
          tone={data.composites_pending > 0 ? "warning" : "positive"}
          onClick={() => onNavigate("composites")}
        />
        <ScoreCard
          label="Draft change sets"
          value={data.change_sets_draft}
          icon={<IconGitBranch className="h-5 w-5" />}
          tone="neutral"
          onClick={() => onNavigate("changes")}
        />
        <div className="flex items-center gap-4 rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
          {data.room_utilisation_pct != null ? (
            <div className="relative flex h-14 w-14 shrink-0 items-center justify-center">
              <Ring percent={data.room_utilisation_pct} size={56} strokeWidth={6} />
              <span className="absolute text-xs font-semibold text-slate-700">{data.room_utilisation_pct}%</span>
            </div>
          ) : (
            <div className="flex h-14 w-14 shrink-0 items-center justify-center rounded-full bg-slate-50 text-slate-300">
              <IconDoor className="h-6 w-6" />
            </div>
          )}
          <div>
            <p className="text-sm font-medium text-slate-900">Room utilisation</p>
            <p className="text-xs text-slate-500">Average across all rooms and lesson slots</p>
          </div>
        </div>
      </div>

      <div className="mb-6 grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-8">
        <StatTile icon={<IconUsers className="h-4 w-4" />} label="Teachers" value={data.counts.teachers} />
        <StatTile icon={<IconUsers className="h-4 w-4" />} label="Students" value={data.counts.students} />
        <StatTile icon={<IconDoor className="h-4 w-4" />} label="Rooms" value={data.counts.rooms} />
        <StatTile icon={<IconLayers className="h-4 w-4" />} label="Roll classes" value={data.counts.roll_classes} />
        <StatTile icon={<IconLayers className="h-4 w-4" />} label="Class offerings" value={data.counts.class_names} />
        <StatTile icon={<IconCalendar className="h-4 w-4" />} label="Lessons / cycle" value={data.counts.lessons} />
        <StatTile icon={<IconCalendar className="h-4 w-4" />} label="Days / cycle" value={data.counts.days} />
        <StatTile icon={<IconCalendar className="h-4 w-4" />} label="Periods / day" value={data.counts.periods_per_day} />
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
          <h3 className="mb-3 text-sm font-semibold text-slate-700">Quick actions</h3>
          <div className="flex flex-col gap-2">
            <QuickAction label="Review open findings" onClick={() => onNavigate("findings")} />
            <QuickAction label="Review composite classes" onClick={() => onNavigate("composites")} />
            <QuickAction label="Import a new export" icon={<IconUpload className="h-4 w-4" />} onClick={onImportClick} />
          </div>
        </div>

        <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
          <h3 className="mb-3 text-sm font-semibold text-slate-700">Recent activity</h3>
          {recentEvents.length === 0 ? (
            <p className="text-xs text-slate-400">No audit events yet.</p>
          ) : (
            <div className="flex flex-col gap-2">
              {recentEvents.map((e) => (
                <div key={e.id} className="text-xs">
                  <span className="font-medium text-slate-700">{EVENT_TYPE_LABELS[e.event_type] ?? e.event_type}</span>
                  <span className="ml-2 text-slate-400">{e.occurred_at}</span>
                  <p className="text-slate-500">{e.summary}</p>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

type Tone = "critical" | "warning" | "positive" | "neutral";

const TONE_CLASSES: Record<Tone, { icon: string; value: string }> = {
  critical: { icon: "bg-red-50 text-red-600", value: "text-red-700" },
  warning: { icon: "bg-amber-50 text-amber-600", value: "text-amber-700" },
  positive: { icon: "bg-emerald-50 text-emerald-600", value: "text-emerald-700" },
  neutral: { icon: "bg-sky-50 text-sky-600", value: "text-slate-900" },
};

function ScoreCard({
  label,
  value,
  icon,
  tone,
  detail,
  onClick,
}: {
  label: string;
  value: number;
  icon: ReactNode;
  tone: Tone;
  detail?: string;
  onClick?: () => void;
}) {
  const classes = TONE_CLASSES[tone];
  return (
    <button
      type="button"
      onClick={onClick}
      className="flex flex-col gap-2 rounded-lg border border-slate-200 bg-white p-4 text-left shadow-sm transition-shadow duration-150 hover:shadow-md"
    >
      <div className="flex items-center justify-between">
        <span className={`flex h-9 w-9 items-center justify-center rounded-lg ${classes.icon}`}>{icon}</span>
        <span className={`text-2xl font-semibold ${classes.value}`}>{value}</span>
      </div>
      <div>
        <p className="text-sm font-medium text-slate-900">{label}</p>
        {detail && <p className="mt-0.5 text-xs text-slate-500">{detail}</p>}
      </div>
    </button>
  );
}

function StatTile({ icon, label, value }: { icon: ReactNode; label: string; value: number }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-3 shadow-sm">
      <div className="mb-1 text-slate-400">{icon}</div>
      <div className="text-lg font-semibold text-slate-900">{value}</div>
      <div className="text-xs text-slate-500">{label}</div>
    </div>
  );
}

function QuickAction({ label, icon, onClick }: { label: string; icon?: ReactNode; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="flex items-center gap-2 rounded-md border border-slate-200 px-3 py-2 text-left text-sm font-medium text-slate-700 transition-colors duration-150 hover:border-sky-300 hover:bg-sky-50 hover:text-sky-700"
    >
      {icon}
      {label}
    </button>
  );
}
