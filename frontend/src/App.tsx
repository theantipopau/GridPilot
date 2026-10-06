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
  fetchTeacherCapabilityCandidates,
  fetchTeachingRequirementCandidates,
} from "./api";
import { Alert, Button } from "./ui";
import CommandPalette from "./components/CommandPalette";
import ImportPanel from "./components/ImportPanel";
import LoadingState from "./components/LoadingState";
import Sidebar, { type SidebarGroup, type Tab } from "./components/Sidebar";
import {
  IconAlertTriangle,
  IconBarChart,
  IconBuilding,
  IconCalendar,
  IconCheckCircle,
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
import TeacherCapabilitiesPage from "./pages/TeacherCapabilitiesPage";
import TeacherLoadsPage from "./pages/TeacherLoadsPage";
import TeachersPage from "./pages/TeachersPage";
import TeachingRequirementsPage from "./pages/TeachingRequirementsPage";
import TimetablePage from "./pages/TimetablePage";
import type { Finding, IngestStatus, ReferenceData, SuggestionCandidate, ViewType } from "./types";

// Navigation is ordered by the workflow the product actually follows
// (docs/ui-ux-audit.md §1.1): read the grid, investigate what the rules
// engine found, test proposals, then approve and keep the audit trail.
// Specialist analysis pages are still here - they just stop competing with
// the main path by sitting in their own group at the bottom.
const SIDEBAR_GROUPS: SidebarGroup[] = [
  { title: "Overview", items: [{ id: "dashboard", label: "Dashboard", icon: (c) => <IconHome className={c} />, description: "What is loaded and what needs attention" }] },
  {
    title: "Review timetable",
    items: [
      { id: "timetable", label: "Master grid", icon: (c) => <IconCalendar className={c} />, description: "Inspect the whole school's lessons" },
      { id: "teachers", label: "Teachers", icon: (c) => <IconUsers className={c} /> },
      { id: "teacher-loads", label: "Teacher loads", icon: (c) => <IconBarChart className={c} /> },
      { id: "rooms", label: "Rooms", icon: (c) => <IconBuilding className={c} /> },
    ],
  },
  {
    title: "Investigate findings",
    items: [
      { id: "findings", label: "Findings", icon: (c) => <IconAlertTriangle className={c} />, description: "Everything the rules engine flagged" },
      { id: "composites", label: "Composite review", icon: (c) => <IconLayers className={c} /> },
      { id: "room-constraints", label: "Room constraints", icon: (c) => <IconDoor className={c} /> },
      { id: "teacher-capabilities", label: "Teacher capabilities", icon: (c) => <IconCheckCircle className={c} /> },
      { id: "teaching-requirements", label: "Teaching requirements", icon: (c) => <IconClipboardList className={c} /> },
    ],
  },
  {
    title: "Test & approve changes",
    items: [{ id: "changes", label: "Change sets", icon: (c) => <IconGitBranch className={c} />, description: "Compare, validate, approve or reject" }],
  },
  { title: "Export & audit", items: [{ id: "audit", label: "Audit", icon: (c) => <IconClipboardList className={c} /> }] },
  {
    title: "Specialist",
    items: [
      { id: "blocking", label: "Blocking", icon: (c) => <IconColumns className={c} /> },
      { id: "staffing-policy", label: "Staffing policy", icon: (c) => <IconClipboardList className={c} /> },
    ],
  },
];

const KNOWN_TABS = new Set<string>(SIDEBAR_GROUPS.flatMap((g) => g.items.map((i) => i.id)));

/** Deep links: `#/findings` opens the findings queue, `#/timetable?scenario=6`
 *  opens the master grid rendering draft change set 6. The hash is the one
 *  piece of location state a router-free app can keep honest - it gives
 *  Back/Forward, refresh-safe state and linkable queues without adding a
 *  router dependency. Non-route hashes (the skip link's `#main-content`) are
 *  ignored rather than treated as navigation. */
function parseHash(): { tab: Tab | null; scenario: number | null } {
  const raw = window.location.hash.replace(/^#\/?/, "");
  const [tabPart, query] = raw.split("?");
  const tab = KNOWN_TABS.has(tabPart) ? (tabPart as Tab) : null;
  const scenarioRaw = new URLSearchParams(query ?? "").get("scenario");
  const scenario = scenarioRaw && /^\d+$/.test(scenarioRaw) ? Number(scenarioRaw) : null;
  return { tab, scenario };
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
  roomConstraints: number;
  teacherCapabilities: number;
  teachingRequirements: number;
  changes: number;
}

export default function App() {
  const [reference, setReference] = useState<ReferenceData | null>(null);
  const [ingestStatus, setIngestStatus] = useState<IngestStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTabState] = useState<Tab>(() => parseHash().tab ?? "dashboard");
  const [gridChangeSetId, setGridChangeSetIdState] = useState<number | null>(() => parseHash().scenario);

  /** One writer for the URL so address bar, Back button and app state can't
   *  drift apart: the active tab is always `#/tab`, and the timetable keeps
   *  an active scenario in `?scenario=`. */
  const writeHash = (nextTab: Tab, scenario: number | null) => {
    const target = scenario != null && nextTab === "timetable" ? `#/timetable?scenario=${scenario}` : `#/${nextTab}`;
    if (window.location.hash !== target) window.location.hash = target;
  };

  // Navigation writes to the hash so Back/Forward move between pages and a
  // queue can be linked to directly. Unknown hashes (the skip link's
  // #main-content) are ignored instead of teleporting the user.
  const setTab = (next: Tab) => {
    setTabState(next);
    writeHash(next, gridChangeSetId);
  };

  const setGridChangeSetId = (id: number | null) => {
    setGridChangeSetIdState(id);
    writeHash(tab, id);
  };

  useEffect(() => {
    const onHashChange = () => {
      const raw = window.location.hash;
      if (raw === "" || raw === "#") {
        setTabState("dashboard");
        return;
      }
      const parsed = parseHash();
      if (parsed.tab) setTabState(parsed.tab);
      setGridChangeSetIdState(parsed.scenario);
    };
    window.addEventListener("hashchange", onHashChange);
    return () => window.removeEventListener("hashchange", onHashChange);
  }, []);
  const [proposeFixContext, setProposeFixContext] = useState<ProposeFixContext | null>(null);
  const [openChangeSetId, setOpenChangeSetId] = useState<number | null>(null);
  const [showImportModal, setShowImportModal] = useState(false);
  const [badgeCounts, setBadgeCounts] = useState<BadgeCounts>({
    findings: 0, composites: 0, roomConstraints: 0, teacherCapabilities: 0, teachingRequirements: 0, changes: 0,
  });
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
      fetchTeacherCapabilityCandidates("REVIEW_REQUIRED").then((r) => r.candidates.length),
      fetchTeachingRequirementCandidates("PENDING").then((r) => r.candidates.length),
      fetchChangeSets().then((r) => r.change_sets.filter((c) => c.approval_status === "DRAFT").length),
    ])
      .then(([findings, composites, roomConstraints, teacherCapabilities, teachingRequirements, changes]) =>
        setBadgeCounts({ findings, composites, roomConstraints, teacherCapabilities, teachingRequirements, changes }),
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
      after_teacher_code:
        candidate.after.teacher_code !== candidate.before.teacher_code ? candidate.after.teacher_code ?? undefined : undefined,
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
      <div className="flex min-h-dvh items-center justify-center bg-canvas p-6">
        <div className="w-full max-w-xl">
          <Alert
            tone="critical"
            title="GridPilot could not reach the local API"
            action={
              <Button variant="primary" size="sm" onClick={() => window.location.reload()}>
                Retry
              </Button>
            }
          >
            <p>{error}</p>
            <p className="mt-1">
              Is the backend running? <code className="text-code rounded bg-surface px-1">python -m uvicorn app.api.main:app --port 8000</code>{" "}
              from <code className="text-code rounded bg-surface px-1">backend/</code>.
            </p>
          </Alert>
        </div>
      </div>
    );
  }

  if (!ingestStatus) {
    return <LoadingState variant="screen" />;
  }

  if (!ingestStatus.has_data) {
    return <ImportPanel variant="onboarding" onImported={handleImported} />;
  }

  if (!reference) {
    return <LoadingState variant="screen" />;
  }

  const badgeFor = (id: Tab): number => {
    if (id === "findings") return badgeCounts.findings;
    if (id === "composites") return badgeCounts.composites;
    if (id === "room-constraints") return badgeCounts.roomConstraints;
    if (id === "teacher-capabilities") return badgeCounts.teacherCapabilities;
    if (id === "teaching-requirements") return badgeCounts.teachingRequirements;
    if (id === "changes") return badgeCounts.changes;
    return 0;
  };

  return (
    <div className="flex h-dvh bg-canvas print:block print:h-auto">
      {/* Keyboard users otherwise meet ~30 nav stops before any content. */}
      <a
        href="#main-content"
        className="sr-only z-[70] rounded-md border border-border bg-surface px-3 py-2 text-sm font-medium text-text-primary shadow-lg focus:not-sr-only focus:absolute focus:left-3 focus:top-3"
      >
        Skip to content
      </a>
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
      <main
        id="main-content"
        tabIndex={-1}
        className="min-h-0 min-w-0 flex-1 overflow-y-auto outline-none print:h-auto print:overflow-visible"
      >
        {showImportModal && (
          <ImportPanel variant="modal" onImported={handleImported} onClose={() => setShowImportModal(false)} />
        )}
        {/* Keyed on the tab so each navigation replays one short entrance -
            the page you asked for arrives, instead of swapping in place. */}
        <div key={tab} className="h-full animate-page-in print:h-auto">
          {tab === "dashboard" && (
            <DashboardPage
              onNavigate={(t) => setTab(t)}
              onImportClick={() => setShowImportModal(true)}
              ingestStatus={ingestStatus}
              queueCounts={badgeCounts}
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
          {tab === "teacher-loads" && (
            <TeacherLoadsPage
              onOpenTimetable={(code) => {
                setJumpTarget({ view: "teacher", code });
                setTab("timetable");
              }}
            />
          )}
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
          {tab === "teacher-capabilities" && <TeacherCapabilitiesPage />}
          {tab === "teaching-requirements" && <TeachingRequirementsPage />}
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
      </main>
    </div>
  );
}
