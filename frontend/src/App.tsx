import { useEffect, useState } from "react";
import { addProposedChange, createChangeSet, fetchReference } from "./api";
import gridPilotLogo from "./assets/gridpilot-logo.png";
import AuditPage from "./pages/AuditPage";
import CompositeReviewPage from "./pages/CompositeReviewPage";
import ChangeSetsPage, { type ProposeFixContext } from "./pages/ChangeSetsPage";
import FindingsPage from "./pages/FindingsPage";
import TimetablePage from "./pages/TimetablePage";
import type { Finding, ReferenceData, SuggestionCandidate } from "./types";

type Tab = "timetable" | "findings" | "composites" | "changes" | "audit";

const TABS: { id: Tab; label: string }[] = [
  { id: "timetable", label: "Timetable" },
  { id: "findings", label: "Findings" },
  { id: "composites", label: "Composite Review" },
  { id: "changes", label: "Change Sets" },
  { id: "audit", label: "Audit" },
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

export default function App() {
  const [reference, setReference] = useState<ReferenceData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<Tab>("timetable");
  const [proposeFixContext, setProposeFixContext] = useState<ProposeFixContext | null>(null);
  const [openChangeSetId, setOpenChangeSetId] = useState<number | null>(null);

  useEffect(() => {
    fetchReference().then(setReference).catch((e) => setError(String(e)));
  }, []);

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
    setOpenChangeSetId(id);
    setTab("changes");
  };

  if (error) {
    return (
      <div className="p-6 text-red-600">
        Failed to load: {error}. Is the backend running (
        <code>python -m uvicorn app.api.main:app --port 8000</code> from <code>backend/</code>)?
      </div>
    );
  }

  if (!reference) {
    return <div className="p-6 text-slate-500">Loading…</div>;
  }

  return (
    <div className="min-h-screen bg-slate-50">
      <header className="flex items-center justify-between border-b border-slate-200 bg-white px-6 py-3">
        <img src={gridPilotLogo} alt="GridPilot" className="h-8 w-auto" />
        <p className="text-sm font-medium text-slate-700">Sophia College</p>
      </header>
      <nav className="flex gap-1 border-b border-slate-200 bg-white px-6">
        {TABS.map((t) => (
          <button
            key={t.id}
            type="button"
            onClick={() => setTab(t.id)}
            className={`px-3 py-2 text-sm font-medium ${
              tab === t.id ? "border-b-2 border-sky-600 text-sky-700" : "text-slate-500 hover:text-slate-700"
            }`}
          >
            {t.label}
          </button>
        ))}
      </nav>
      {tab === "timetable" && <TimetablePage reference={reference} />}
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
