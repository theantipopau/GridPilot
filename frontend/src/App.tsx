import { useEffect, useState, type ReactNode } from "react";
import {
  addProposedChange,
  createChangeSet,
  fetchChangeSets,
  fetchCompositeCandidates,
  fetchFindings,
  fetchIngestStatus,
  fetchReference,
} from "./api";
import gridPilotLogo from "./assets/gridpilot-logo.png";
import ImportPanel from "./components/ImportPanel";
import LoadingState from "./components/LoadingState";
import { IconAlertTriangle, IconCalendar, IconClipboardList, IconGitBranch, IconLayers, IconUpload } from "./components/icons";
import AuditPage from "./pages/AuditPage";
import CompositeReviewPage from "./pages/CompositeReviewPage";
import ChangeSetsPage, { type ProposeFixContext } from "./pages/ChangeSetsPage";
import FindingsPage from "./pages/FindingsPage";
import TimetablePage from "./pages/TimetablePage";
import type { Finding, IngestStatus, ReferenceData, SuggestionCandidate } from "./types";

type Tab = "timetable" | "findings" | "composites" | "changes" | "audit";

const TABS: { id: Tab; label: string; icon: (className?: string) => ReactNode }[] = [
  { id: "timetable", label: "Timetable", icon: (c) => <IconCalendar className={c} /> },
  { id: "findings", label: "Findings", icon: (c) => <IconAlertTriangle className={c} /> },
  { id: "composites", label: "Composite Review", icon: (c) => <IconLayers className={c} /> },
  { id: "changes", label: "Change Sets", icon: (c) => <IconGitBranch className={c} /> },
  { id: "audit", label: "Audit", icon: (c) => <IconClipboardList className={c} /> },
];

function sourceFileName(path: string | null): string | null {
  if (!path) return null;
  const base = path.split(/[\\/]/).pop() ?? path;
  // Browser-uploaded files are staged on disk with a "<timestamp>_" prefix
  // for collision-safety (see app/api/ingest.py) - strip it back off for
  // display so it reads as the file the user actually chose.
  return base.replace(/^\d{8}T\d{12}_/, "");
}

function buildProposeFixContext(finding: Finding): ProposeFixContext {
  const byType = (type: string) => finding.entity_refs.find((r) => r.type === type)?.code;
  const slot = finding.slot_refs[0];
  return {
    findingId: finding.id,
    suggestedName: finding.title,
    dayCode: slot?.day_code,
    periodCode: slot?.period_code,
    teacherCode: byType("teacher"),
    roomCode: byType("room"),
    classCode: byType("class"),
  };
}

interface BadgeCounts {
  findings: number;
  composites: number;
  changes: number;
}

export default function App() {
  const [reference, setReference] = useState<ReferenceData | null>(null);
  const [ingestStatus, setIngestStatus] = useState<IngestStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<Tab>("timetable");
  const [proposeFixContext, setProposeFixContext] = useState<ProposeFixContext | null>(null);
  const [openChangeSetId, setOpenChangeSetId] = useState<number | null>(null);
  const [showImportModal, setShowImportModal] = useState(false);
  const [badgeCounts, setBadgeCounts] = useState<BadgeCounts>({ findings: 0, composites: 0, changes: 0 });
  const [gridChangeSetId, setGridChangeSetId] = useState<number | null>(null);

  const openChangeSetInTab = (id: number) => {
    setOpenChangeSetId(id);
    setTab("changes");
  };

  // Sequenced, not parallel: fetching reference data before we know an
  // import has ever happened would 503 against a schema-less database
  // (see app/api/deps.py's _require_schema_initialized) - status always
  // comes first, and reference only follows once there's something to load.
  const loadAll = () => {
    fetchIngestStatus()
      .then((status) => {
        setIngestStatus(status);
        if (status.has_data) return fetchReference().then(setReference);
      })
      .catch((e) => setError(String(e)));
  };

  useEffect(loadAll, []);

  useEffect(() => {
    if (!ingestStatus?.has_data) return;
    Promise.all([
      fetchFindings().then((r) => r.total),
      fetchCompositeCandidates("PENDING").then((r) => r.candidates.length),
      fetchChangeSets().then((r) => r.change_sets.filter((c) => c.approval_status === "DRAFT").length),
    ])
      .then(([findings, composites, changes]) => setBadgeCounts({ findings, composites, changes }))
      .catch(() => {
        // Badge counts are a convenience, not core data - a transient failure here shouldn't block the tab.
      });
  }, [tab, ingestStatus?.has_data]);

  const handleApplySuggestion = async (finding: Finding, candidate: SuggestionCandidate) => {
    const { id } = await createChangeSet(`${finding.title} (suggested fix)`, undefined, "you");
    await addProposedChange(id, {
      timetable_entry_id: candidate.entry_id,
      after_day_code: candidate.after.day_code,
      after_period_code: candidate.after.period_code,
      after_room_code: candidate.after.room_code ?? undefined,
      reason: "Applied from a suggested fix",
      finding_ids: [finding.id],
    });
    openChangeSetInTab(id);
  };

  const handleImported = () => {
    setShowImportModal(false);
    setTab("timetable");
    loadAll();
  };

  if (error) {
    return (
      <div className="p-6 text-red-600">
        Failed to load: {error}. Is the backend running (
        <code>python -m uvicorn app.api.main:app --port 8000</code> from <code>backend/</code>)?
      </div>
    );
  }

  if (!ingestStatus) {
    return <LoadingState />;
  }

  if (!ingestStatus.has_data) {
    return <ImportPanel variant="onboarding" onImported={handleImported} />;
  }

  if (!reference) {
    return <LoadingState />;
  }

  const badgeFor = (id: Tab): number => {
    if (id === "findings") return badgeCounts.findings;
    if (id === "composites") return badgeCounts.composites;
    if (id === "changes") return badgeCounts.changes;
    return 0;
  };

  return (
    <div className="min-h-screen bg-slate-50">
      <header className="flex flex-wrap items-center gap-x-6 gap-y-2 border-b border-slate-200 bg-white px-6 py-3">
        <img src={gridPilotLogo} alt="GridPilot" className="h-8 w-auto" />
        <nav className="flex flex-1 gap-1">
          {TABS.map((t) => {
            const count = badgeFor(t.id);
            const active = tab === t.id;
            return (
              <button
                key={t.id}
                type="button"
                onClick={() => setTab(t.id)}
                className={`flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm font-medium transition-colors duration-150 ${
                  active ? "bg-sky-50 text-sky-700" : "text-slate-500 hover:bg-slate-50 hover:text-slate-700"
                }`}
              >
                {t.icon(active ? "h-4 w-4 text-sky-600" : "h-4 w-4 text-slate-400")}
                {t.label}
                {count > 0 && (
                  <span
                    className={`rounded-full px-1.5 py-0.5 text-xs font-semibold transition-colors duration-150 ${
                      active ? "bg-sky-600 text-white" : "bg-slate-200 text-slate-600"
                    }`}
                  >
                    {count}
                  </span>
                )}
              </button>
            );
          })}
        </nav>
        <div className="flex items-center gap-3 text-right">
          <div className="hidden sm:block">
            <p className="text-xs font-medium text-slate-600">
              {sourceFileName(ingestStatus.last_ingest?.tfx_source_path ?? null) ?? "No file loaded"}
            </p>
            <p className="text-xs text-slate-400">
              {ingestStatus.last_ingest?.finished_at
                ? `Imported ${new Date(ingestStatus.last_ingest.finished_at).toLocaleString()}`
                : "Sophia College"}
            </p>
          </div>
          <button
            type="button"
            onClick={() => setShowImportModal(true)}
            className="flex items-center gap-1.5 rounded-md border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-700 transition-colors duration-150 hover:border-slate-400 hover:bg-slate-50"
          >
            <IconUpload className="h-4 w-4" />
            Import…
          </button>
        </div>
      </header>
      {showImportModal && (
        <ImportPanel variant="modal" onImported={handleImported} onClose={() => setShowImportModal(false)} />
      )}
      {tab === "timetable" && (
        <TimetablePage
          reference={reference}
          gridChangeSetId={gridChangeSetId}
          onGridChangeSetCreated={setGridChangeSetId}
          onOpenChangeSet={openChangeSetInTab}
        />
      )}
      {tab === "findings" && (
        <FindingsPage
          onProposeFix={(finding) => {
            setProposeFixContext(buildProposeFixContext(finding));
            setTab("changes");
          }}
          onApplySuggestion={handleApplySuggestion}
        />
      )}
      {tab === "composites" && <CompositeReviewPage />}
      {tab === "changes" && (
        <ChangeSetsPage
          reference={reference}
          proposeFixContext={proposeFixContext}
          onConsumeProposeFixContext={() => setProposeFixContext(null)}
          openChangeSetId={openChangeSetId}
        />
      )}
      {tab === "audit" && <AuditPage />}
    </div>
  );
}
