import { useState } from "react";
import { explainFinding, fetchSuggestions } from "../api";
import EmptyState from "./EmptyState";
import { IconCheckCircle } from "./icons";
import type { Finding, Severity, SuggestionCandidate, SuggestionsResponse } from "../types";

interface Props {
  findings: Finding[];
  countsBySeverity: Record<Severity, number>;
  onProposeFix?: (finding: Finding) => void;
  onApplySuggestion?: (finding: Finding, candidate: SuggestionCandidate) => Promise<void>;
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

export default function FindingsList({ findings, countsBySeverity, onProposeFix, onApplySuggestion }: Props) {
  const [suggestionsByFinding, setSuggestionsByFinding] = useState<Record<number, SuggestionsResponse | "loading">>({});
  const [applyingKey, setApplyingKey] = useState<string | null>(null);
  const [explanationsByFinding, setExplanationsByFinding] = useState<Record<number, ExplanationState>>({});

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
          title="No open findings"
          description="The rules engine found no clashes in the current timetable."
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
                </div>
              </div>

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
                    <div className="flex flex-col gap-1">
                      {suggestions.candidates.map((c, i) => {
                        const key = `${f.id}:${c.entry_id}:${c.after.day_code}:${c.after.period_code}:${c.after.room_code}`;
                        return (
                          <div key={i} className="flex items-center justify-between gap-2 rounded bg-white px-2 py-1 text-xs">
                            <span>
                              {c.class_code}: {c.before.day_code} {c.before.period_code} {c.before.room_code}
                              <span className="mx-1 opacity-50">→</span>
                              {c.after.day_code} {c.after.period_code} {c.after.room_code}
                              <span className="ml-1 opacity-50">
                                ({c.movement_cost === 0 ? "room only" : c.movement_cost === 1 ? "same day" : "different day"})
                              </span>
                            </span>
                            {onApplySuggestion && (
                              <button
                                type="button"
                                onClick={() => applySuggestion(f, c)}
                                disabled={applyingKey === key}
                                className="shrink-0 rounded bg-sky-600 px-2 py-1 font-medium text-white disabled:opacity-50"
                              >
                                {applyingKey === key ? "Applying…" : "Use this"}
                              </button>
                            )}
                          </div>
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
