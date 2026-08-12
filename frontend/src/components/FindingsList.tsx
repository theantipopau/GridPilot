import { useState } from "react";
import { acceptFindingRisk, explainFinding, fetchSuggestions, reopenFinding } from "../api";
import EmptyState from "./EmptyState";
import SuggestionCandidateCard from "./SuggestionCandidateCard";
import { IconCheckCircle } from "./icons";
import type { Finding, Severity, SuggestionCandidate, SuggestionsResponse } from "../types";

interface Props {
  findings: Finding[];
  countsBySeverity: Record<Severity, number>;
  reviewedBy?: string;
  onProposeFix?: (finding: Finding) => void;
  onApplySuggestion?: (finding: Finding, candidate: SuggestionCandidate) => Promise<void>;
  onReviewed?: () => void;
}

const SEVERITY_STYLES: Record<Severity, string> = {
  critical: "bg-red-50 border-red-200 text-red-800",
  warning: "bg-amber-50 border-amber-200 text-amber-800",
  info: "bg-slate-50 border-slate-200 text-slate-600",
};

const SEVERITY_BADGE: Record<Severity, string> = {
  critical: "bg-red-600 text-white",
  warning: "bg-amber-500 text-white",
  info: "bg-slate-400 text-white",
};

type ExplanationState = { status: "loading" } | { status: "done"; text: string } | { status: "error"; message: string };

export default function FindingsList({
  findings,
  countsBySeverity,
  reviewedBy,
  onProposeFix,
  onApplySuggestion,
  onReviewed,
}: Props) {
  const [suggestionsByFinding, setSuggestionsByFinding] = useState<Record<number, SuggestionsResponse | "loading">>({});
  const [applyingKey, setApplyingKey] = useState<string | null>(null);
  const [explanationsByFinding, setExplanationsByFinding] = useState<Record<number, ExplanationState>>({});
  const [reviewingId, setReviewingId] = useState<number | null>(null);

  const toggleSuggestions = async (finding: Finding) => {
    const current = suggestionsByFinding[finding.id];
    if (current) {
      setSuggestionsByFinding((prev) => {
        const next = { ...prev };
        delete next[finding.id];
        return next;
      });
      return;
    }
    setSuggestionsByFinding((prev) => ({ ...prev, [finding.id]: "loading" }));
    const result = await fetchSuggestions(finding.id);
    setSuggestionsByFinding((prev) => ({ ...prev, [finding.id]: result }));
  };

  const toggleExplanation = async (finding: Finding) => {
    const current = explanationsByFinding[finding.id];
    if (current) {
      setExplanationsByFinding((prev) => {
        const next = { ...prev };
        delete next[finding.id];
        return next;
      });
      return;
    }
    setExplanationsByFinding((prev) => ({ ...prev, [finding.id]: { status: "loading" } }));
    try {
      const result = await explainFinding(finding.id);
      setExplanationsByFinding((prev) => ({ ...prev, [finding.id]: { status: "done", text: result.explanation } }));
    } catch (e) {
      setExplanationsByFinding((prev) => ({ ...prev, [finding.id]: { status: "error", message: String(e) } }));
    }
  };

  const handleAcceptRisk = async (finding: Finding) => {
    if (!reviewedBy?.trim()) {
      alert("Enter your name before marking a finding as intentional.");
      return;
    }
    let note: string | null = null;
    try {
      note = window.prompt("Optional note - why is this intentional?");
    } catch {
      // window.prompt isn't available in every embedding context - the note is optional, so just skip it.
    }
    setReviewingId(finding.id);
    try {
      await acceptFindingRisk(finding.id, reviewedBy.trim(), note || undefined);
      onReviewed?.();
    } finally {
      setReviewingId(null);
    }
  };

  const handleReopen = async (finding: Finding) => {
    if (!reviewedBy?.trim()) {
      alert("Enter your name before reopening a finding.");
      return;
    }
    setReviewingId(finding.id);
    try {
      await reopenFinding(finding.id, reviewedBy.trim());
      onReviewed?.();
    } finally {
      setReviewingId(null);
    }
  };

  const applySuggestion = async (finding: Finding, candidate: SuggestionCandidate) => {
    if (!onApplySuggestion) return;
    const key = `${finding.id}:${candidate.entry_id}:${candidate.after.day_code}:${candidate.after.period_code}:${candidate.after.room_code}`;
    setApplyingKey(key);
    try {
      await onApplySuggestion(finding, candidate);
    } finally {
      setApplyingKey(null);
    }
  };

  if (findings.length === 0) {
    return (
      <div className="px-6 pb-6">
        <EmptyState
          tone="positive"
          icon={<IconCheckCircle className="h-8 w-8" />}
          title="No findings here"
          description="Nothing in the current timetable matches this tab."
        />
      </div>
    );
  }

  return (
    <div className="px-6 pb-6">
      <div className="mb-4 flex gap-3 text-sm">
        {(["critical", "warning", "info"] as Severity[]).map((sev) => (
          <span key={sev} className={`rounded-full px-3 py-1 font-medium ${SEVERITY_BADGE[sev]}`}>
            {countsBySeverity[sev]} {sev}
          </span>
        ))}
      </div>
      <div className="flex flex-col gap-2">
        {findings.map((f) => {
          const suggestions = suggestionsByFinding[f.id];
          return (
            <div
              key={f.id}
              className={`rounded-lg border p-3 text-sm shadow-sm transition-shadow duration-150 hover:shadow-md ${SEVERITY_STYLES[f.severity]}`}
            >
              <div className="flex items-center justify-between">
                <span className="font-medium">{f.title}</span>
                <span className="text-xs uppercase tracking-wide opacity-60">{f.rule_id}</span>
              </div>
              <div className="mt-1 flex flex-wrap items-center gap-1">
                {f.entity_refs.map((ref, i) => (
                  <span key={i} className="rounded border border-current/30 px-1.5 py-0.5 text-xs opacity-80">
                    {ref.type}:{ref.code}
                  </span>
                ))}
                <div className="ml-auto flex gap-2">
                  <button
                    type="button"
                    onClick={() => toggleExplanation(f)}
                    className="rounded bg-white/70 px-2 py-1 text-xs font-medium text-current underline hover:bg-white"
                  >
                    {explanationsByFinding[f.id] ? "Hide explanation" : "Explain"}
                  </button>
                  <button
                    type="button"
                    onClick={() => toggleSuggestions(f)}
                    className="rounded bg-white/70 px-2 py-1 text-xs font-medium text-current underline hover:bg-white"
                  >
                    {suggestions ? "Hide suggestions" : "Suggest fixes"}
                  </button>
                  {onProposeFix && (
                    <button
                      type="button"
                      onClick={() => onProposeFix(f)}
                      className="rounded bg-white/70 px-2 py-1 text-xs font-medium text-current underline hover:bg-white"
                    >
                      Propose a fix manually
                    </button>
                  )}
                  {f.status === "ACCEPTED_RISK" ? (
                    <button
                      type="button"
                      disabled={reviewingId === f.id}
                      onClick={() => handleReopen(f)}
                      className="rounded bg-white/70 px-2 py-1 text-xs font-medium text-current underline hover:bg-white disabled:opacity-50"
                    >
                      Reopen
                    </button>
                  ) : (
                    <button
                      type="button"
                      disabled={reviewingId === f.id}
                      onClick={() => handleAcceptRisk(f)}
                      className="rounded bg-white/70 px-2 py-1 text-xs font-medium text-current underline hover:bg-white disabled:opacity-50"
                    >
                      Mark as intentional
                    </button>
                  )}
                </div>
              </div>

              {f.status === "ACCEPTED_RISK" && (
                <div className="mt-1 text-xs opacity-70">
                  Accepted as intentional by {f.reviewed_by}
                  {f.review_note ? ` - "${f.review_note}"` : ""}
                </div>
              )}

              {explanationsByFinding[f.id]?.status === "loading" && (
                <p className="mt-2 text-xs opacity-70">Asking the local AI advisor…</p>
              )}
              {explanationsByFinding[f.id]?.status === "error" && (
                <p className="mt-2 rounded border border-current/20 bg-white/60 p-2 text-xs opacity-70">
                  {(explanationsByFinding[f.id] as { status: "error"; message: string }).message}
                </p>
              )}
              {explanationsByFinding[f.id]?.status === "done" && (
                <p className="mt-2 rounded border border-current/20 bg-white/60 p-2 text-xs">
                  {(explanationsByFinding[f.id] as { status: "done"; text: string }).text}
                </p>
              )}

              {suggestions === "loading" && (
                <p className="mt-2 text-xs opacity-70">Searching for valid alternatives…</p>
              )}
              {suggestions && suggestions !== "loading" && (
                <div className="mt-2 rounded border border-current/20 bg-white/60 p-2">
                  {!suggestions.supported && <p className="text-xs opacity-70">{suggestions.note}</p>}
                  {suggestions.supported && suggestions.candidates.length === 0 && (
                    <p className="text-xs opacity-70">No valid alternative found that doesn't create a new clash.</p>
                  )}
                  {suggestions.supported && suggestions.candidates.length > 0 && (
                    <div className="flex max-h-72 flex-col gap-1.5 overflow-y-auto pr-1">
                      {suggestions.candidates.map((c, i) => {
                        const key = `${f.id}:${c.entry_id}:${c.after.day_code}:${c.after.period_code}:${c.after.room_code}`;
                        return (
                          <SuggestionCandidateCard
                            key={i}
                            candidate={c}
                            onApply={onApplySuggestion ? () => applySuggestion(f, c) : undefined}
                            applying={applyingKey === key}
                          />
                        );
                      })}
                    </div>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
