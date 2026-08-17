import { useEffect, useState } from "react";
import {
  addProposedChange,
  createChangeSet,
  fetchChangeSets,
  fetchCompositeCandidates,
  fetchFindings,
  fetchIngestStatus,
  fetchReference,
  fetchRoomConstraintCandidates,
} from "./api";
import CommandPalette from "./components/CommandPalette";
import ImportPanel from "./components/ImportPanel";
import LoadingState from "./components/LoadingState";
import Sidebar, { type SidebarGroup, type Tab } from "./components/Sidebar";
import {
  IconAlertTriangle,
  IconBuilding,
  IconCalendar,
  IconClipboardList,
  IconColumns,
  IconDoor,
  IconGitBranch,
  IconHome,
  IconLayers,
  IconUsers,
} from "./components/icons";
import AuditPage from "./pages/AuditPage";
import BlockingPage from "./pages/BlockingPage";
import CompositeReviewPage from "./pages/CompositeReviewPage";
import ChangeSetsPage, { type ProposeFixContext } from "./pages/ChangeSetsPage";
import DashboardPage from "./pages/DashboardPage";
import FindingsPage from "./pages/FindingsPage";
import RoomConstraintsPage from "./pages/RoomConstraintsPage";
import RoomsPage from "./pages/RoomsPage";
import StaffingPolicyPage from "./pages/StaffingPolicyPage";
import TeachersPage from "./pages/TeachersPage";
import TimetablePage from "./pages/TimetablePage";
import type { Finding, IngestStatus, ReferenceData, SuggestionCandidate, ViewType } from "./types";

// Grouped per docs/full-timetabler-plan.md §7.1 - the flat list stops
// scaling around 10 items, and this mirrors the school's own mental model
// (structure vs people vs places vs the grid itself vs quality control).
const SIDEBAR_GROUPS: SidebarGroup[] = [
  { title: "Overview", items: [{ id: "dashboard", label: "Dashboard", icon: (c) => <IconHome className={c} /> }] },
  { title: "Structure", items: [{ id: "blocking", label: "Blocking", icon: (c) => <IconColumns className={c} /> }] },
  {
    title: "People",
    items: [
      { id: "teachers", label: "Teachers", icon: (c) => <IconUsers className={c} /> },
      { id: "staffing-policy", label: "Staffing Policy", icon: (c) => <IconClipboardList className={c} /> },
    ],
  },
  { title: "Places", items: [{ id: "rooms", label: "Rooms", icon: (c) => <IconBuilding className={c} /> }] },
  { title: "Timetable", items: [{ id: "timetable", label: "Master grid", icon: (c) => <IconCalendar className={c} /> }] },
  {
    title: "Quality",
    items: [
      { id: "findings", label: "Findings", icon: (c) => <IconAlertTriangle className={c} /> },
      { id: "composites", label: "Composite Review", icon: (c) => <IconLayers className={c} /> },
      { id: "room-constraints", label: "Room Constraints", icon: (c) => <IconDoor className={c} /> },
    ],
  },
  {
    title: "Changes",
    items: [
      { id: "changes", label: "Change Sets", icon: (c) => <IconGitBranch className={c} /> },
      { id: "audit", label: "Audit", icon: (c) => <IconClipboardList className={c} /> },
    ],
  },
];

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
  roomConstraints: number;
  changes: number;
}

export default function App() {
  const [reference, setReference] = useState<ReferenceData | null>(null);
  const [ingestStatus, setIngestStatus] = useState<IngestStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<Tab>("dashboard");
  const [proposeFixContext, setProposeFixContext] = useState<ProposeFixContext | null>(null);
  const [openChangeSetId, setOpenChangeSetId] = useState<number | null>(null);
  const [showImportModal, setShowImportModal] = useState(false);
  const [badgeCounts, setBadgeCounts] = useState<BadgeCounts>({ findings: 0, composites: 0, roomConstraints: 0, changes: 0 });
  const [gridChangeSetId, setGridChangeSetId] = useState<number | null>(null);
  const [showSearch, setShowSearch] = useState(false);
  const [jumpTarget, setJumpTarget] = useState<{ view: ViewType; code: string } | null>(null);

  const openChangeSetInTab = (id: number) => {
    setOpenChangeSetId(id);
    setTab("changes");
  };

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setShowSearch((s) => !s);
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, []);

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
      fetchRoomConstraintCandidates("PENDING").then((r) => r.candidates.length),
      fetchChangeSets().then((r) => r.change_sets.filter((c) => c.approval_status === "DRAFT").length),
    ])
      .then(([findings, composites, roomConstraints, changes]) =>
        setBadgeCounts({ findings, composites, roomConstraints, changes }),
      )
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
    setTab("dashboard");
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
    if (id === "room-constraints") return badgeCounts.roomConstraints;
    if (id === "changes") return badgeCounts.changes;
    return 0;
  };

  return (
    <div className="flex h-screen bg-slate-50">
      <Sidebar
        groups={SIDEBAR_GROUPS}
        activeTab={tab}
        onTabChange={setTab}
        badgeFor={badgeFor}
        ingestStatus={ingestStatus}
        onImportClick={() => setShowImportModal(true)}
        onSearchClick={() => setShowSearch(true)}
      />
      {showSearch && (
        <CommandPalette
          reference={reference}
          onClose={() => setShowSearch(false)}
          onNavigateTab={(t) => setTab(t)}
          onJumpToEntity={(view, code) => {
            setJumpTarget({ view, code });
            setTab("timetable");
          }}
        />
      )}
      {/* min-h-0 is not optional here: a flex item's default min-height is
          `auto` (its content size), which silently overrides flex-1 and
          h-screen on the row above it - main would grow to fit its
          tallest page instead of clipping to the viewport and scrolling
          internally, which is exactly the bug this replaced (verified in
          the browser: without it, a long Findings page grew main to
          12905px and the whole body scrolled underneath a "fixed"
          sidebar that was never actually fixed). */}
      <main className="min-h-0 min-w-0 flex-1 overflow-y-auto">
        {showImportModal && (
          <ImportPanel variant="modal" onImported={handleImported} onClose={() => setShowImportModal(false)} />
        )}
        {tab === "dashboard" && (
          <DashboardPage
            onNavigate={(t) => setTab(t)}
            onImportClick={() => setShowImportModal(true)}
          />
        )}
        {tab === "timetable" && (
          <TimetablePage
            reference={reference}
            gridChangeSetId={gridChangeSetId}
            onGridChangeSetCreated={setGridChangeSetId}
            onOpenChangeSet={openChangeSetInTab}
            jumpTarget={jumpTarget}
            onJumpConsumed={() => setJumpTarget(null)}
          />
        )}
        {tab === "blocking" && <BlockingPage />}
        {tab === "teachers" && <TeachersPage />}
        {tab === "staffing-policy" && <StaffingPolicyPage />}
        {tab === "rooms" && <RoomsPage />}
        {tab === "findings" && (
          <FindingsPage
            onProposeFix={(finding) => {
              setProposeFixContext(buildProposeFixContext(finding));
              setTab("changes");
            }}
            onApplySuggestion={handleApplySuggestion}
            onOpenChangeSet={openChangeSetInTab}
          />
        )}
        {tab === "composites" && <CompositeReviewPage />}
        {tab === "room-constraints" && <RoomConstraintsPage />}
        {tab === "changes" && (
          <ChangeSetsPage
            reference={reference}
            proposeFixContext={proposeFixContext}
            onConsumeProposeFixContext={() => setProposeFixContext(null)}
            openChangeSetId={openChangeSetId}
          />
        )}
        {tab === "audit" && <AuditPage />}
      </main>
    </div>
  );
}
