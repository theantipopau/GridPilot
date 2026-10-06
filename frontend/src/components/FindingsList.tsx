import { useMemo, useState } from "react";
import { acceptFindingRisk, explainFinding, fetchSuggestions, reopenFinding, summarizeFindings } from "../api";
import SuggestionCandidateCard from "./SuggestionCandidateCard";
import { useReviewerGate } from "../lib/reviewer";
import {
  Alert,
  Badge,
  Button,
  DetailSection,
  Drawer,
  EmptyState,
  FilterBar,
  SearchInput,
  cx,
  toneForSeverity,
} from "../ui";
import type { Tone } from "../ui";
import { matchesQuery } from "../lib/search";
import type { Finding, PortfolioExplanation, Severity, SuggestionCandidate, SuggestionsResponse } from "../types";

interface Props {
  findings: Finding[];
  countsBySeverity: Record<Severity, number>;
  onProposeFix?: (finding: Finding) => void;
  onApplySuggestion?: (finding: Finding, candidate: SuggestionCandidate) => Promise<void>;
  onReviewed?: () => void;
}

/** Lifecycle wording a user must be able to read at a glance - the colour is
 *  only ever the second channel (docs/ui-ux-audit.md §6). */
function statusFor(f: Finding): { label: string; tone: Tone } {
  if (f.status === "ACCEPTED_RISK") return { label: "Accepted risk", tone: "warning" };
  return { label: "Newly detected", tone: "info" };
}

type ExplanationState = { status: "loading" } | { status: "done"; text: string } | { status: "error"; message: string };

export default function FindingsList({
  findings,
  countsBySeverity,
  onProposeFix,
  onApplySuggestion,
  onReviewed,
}: Props) {
  const reviewer = useReviewerGate();
  const [suggestionsByFinding, setSuggestionsByFinding] = useState<Record<number, SuggestionsResponse | "loading">>({});
  const [applyingKey, setApplyingKey] = useState<string | null>(null);
  const [explanationsByFinding, setExplanationsByFinding] = useState<Record<number, ExplanationState>>({});
  const [busyId, setBusyId] = useState<number | null>(null);
  const [query, setQuery] = useState("");
  const [severityFilter, setSeverityFilter] = useState<Severity[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [reviewError, setReviewError] = useState<string | null>(null);
  const [portfolio, setPortfolio] = useState<
    { status: "loading" } | { status: "error"; message: string } | { status: "done"; result: PortfolioExplanation } | null
  >(null);

  const filtered = useMemo(
    () =>
      findings.filter(
        (f) =>
          (severityFilter.length === 0 || severityFilter.includes(f.severity)) &&
          matchesQuery(query, [f.title, f.rule_id, ...f.entity_refs.map((r) => r.code)]),
      ),
    [findings, severityFilter, query],
  );

  const selectedIndex = filtered.findIndex((f) => f.id === selectedId);
  const selected = selectedIndex >= 0 ? filtered[selectedIndex] : null;
  const step = (delta: number) => {
    if (selectedIndex < 0 || filtered.length === 0) return;
    const next = (selectedIndex + delta + filtered.length) % filtered.length;
    setSelectedId(filtered[next].id);
  };

  // Summarize exactly what's currently visible - whichever severity filter
  // and search the user has applied - not every finding in the database.
  const summarizeVisible = async () => {
    setPortfolio({ status: "loading" });
    try {
      const result = await summarizeFindings(filtered.map((f) => f.id));
      setPortfolio({ status: "done", result });
    } catch (e) {
      setPortfolio({ status: "error", message: String(e) });
    }
  };

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
    if (!reviewer.check()) return;
    setBusyId(finding.id);
    setReviewError(null);
    try {
      // The note stays optional and is asked in-page: window.prompt blocks
      // the whole app and can't be styled or keyboard-tested.
      const note = window.prompt("Optional note - why is this intentional?") || undefined;
      await acceptFindingRisk(finding.id, reviewer.reviewer, note);
      onReviewed?.();
    } catch (e) {
      setReviewError(String(e));
    } finally {
      setBusyId(null);
    }
  };

  const handleReopen = async (finding: Finding) => {
    if (!reviewer.check()) return;
    setBusyId(finding.id);
    setReviewError(null);
    try {
      await reopenFinding(finding.id, reviewer.reviewer);
      onReviewed?.();
    } catch (e) {
      setReviewError(String(e));
    } finally {
      setBusyId(null);
    }
  };

  const applySuggestion = async (finding: Finding, candidate: SuggestionCandidate) => {
    if (!onApplySuggestion) return;
    const key = `${finding.id}:${candidate.entry_id}:${candidate.after.day_code}:${candidate.after.period_code}:${candidate.after.room_code}:${candidate.after.teacher_code}`;
    setApplyingKey(key);
    try {
      await onApplySuggestion(finding, candidate);
    } finally {
      setApplyingKey(null);
    }
  };

  const chips = [
    ...severityFilter.map((sev) => ({
      id: `sev-${sev}`,
      label: `${sev}: ${countsBySeverity[sev]}`,
      onRemove: () => setSeverityFilter((prev) => prev.filter((s) => s !== sev)),
    })),
  ];

  if (findings.length === 0) {
    return (
      <EmptyState
        tone="positive"
        className="mx-6 mb-6"
        title="No findings here"
        description="Nothing in the current timetable matches this tab."
      />
    );
  }

  return (
    <div className="px-6 pb-6">
      <FilterBar
        className="mb-3"
        search={
          <SearchInput
            value={query}
            onChange={setQuery}
            placeholder="Search title, rule, or entity code…"
            resultCount={filtered.length}
            totalCount={findings.length}
          />
        }
        chips={chips}
        onClearAll={chips.length > 0 || query ? () => {
          setSeverityFilter([]);
          setQuery("");
        } : undefined}
        count={`${filtered.length} of ${findings.length}`}
      >
        {/* Severity doubles as a filter: clicking narrows the list instead of
            navigating away, so triage stays in one place. */}
        <div className="flex flex-wrap gap-1.5">
          {(["critical", "warning", "info"] as Severity[]).map((sev) => {
            const active = severityFilter.includes(sev);
            return (
              <button
                key={sev}
                type="button"
                aria-pressed={active}
                onClick={() =>
                  setSeverityFilter((prev) => (prev.includes(sev) ? prev.filter((s) => s !== sev) : [...prev, sev]))
                }
                className={cx(
                  "rounded-full border px-2.5 py-1 text-xs font-medium transition-colors duration-150",
                  "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus",
                  active
                    ? "border-brand-border bg-brand text-brand-contrast"
                    : "border-border bg-surface text-text-secondary hover:bg-hovered",
                )}
              >
                <span className="nums">{countsBySeverity[sev]}</span> {sev}
              </button>
            );
          })}
        </div>
        <Button
          size="sm"
          variant="ghost"
          onClick={summarizeVisible}
          disabled={filtered.length === 0 || portfolio?.status === "loading"}
          title="Ask the local AI advisor to summarise the shape of the findings currently shown here"
        >
          {portfolio?.status === "loading" ? "Summarizing…" : `Summarize these ${filtered.length}`}
        </Button>
      </FilterBar>

      {reviewError && (
        <Alert tone="critical" className="mb-3" onDismiss={() => setReviewError(null)}>
          {reviewError}
        </Alert>
      )}

      {portfolio && (
        <div className="mb-3 rounded-lg border border-border bg-surface p-3 text-sm">
          {portfolio.status === "loading" && <p className="text-meta">Asking the local AI advisor…</p>}
          {portfolio.status === "error" && (
            <Alert tone="critical">{portfolio.message}</Alert>
          )}
          {portfolio.status === "done" && (
            <>
              <p className="text-body">{portfolio.result.explanation}</p>
              {portfolio.result.summary.top_entities.length > 0 && (
                <div className="mt-2 flex flex-wrap gap-1.5">
                  {portfolio.result.summary.top_entities.slice(0, 8).map((e) => (
                    <Badge key={`${e.type}:${e.code}`} size="sm" tone="neutral" variant="outline" title={`Appears in ${e.count} of the ${portfolio.result.summary.total_count} findings summarised`}>
                      {e.type}:{e.code} · {e.count}
                    </Badge>
                  ))}
                </div>
              )}
            </>
          )}
        </div>
      )}

      {filtered.length === 0 ? (
        <EmptyState
          title="No findings match your filters"
          description="Remove a severity chip or clear the search to see the rest."
          action={
            <Button
              size="sm"
              onClick={() => {
                setSeverityFilter([]);
                setQuery("");
              }}
            >
              Clear filters
            </Button>
          }
        />
      ) : (
        <ul className="flex flex-col gap-2">
          {filtered.map((f) => {
            const status = statusFor(f);
            return (
              <li key={f.id}>
                <button
                  type="button"
                  onClick={() => setSelectedId(f.id)}
                  className={cx(
                    "flex w-full items-start gap-3 rounded-lg border border-border bg-surface p-3 text-left",
                    "transition-colors duration-150 hover:border-border-strong hover:bg-hovered",
                    "focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-focus",
                    selectedId === f.id && "border-brand-border bg-selected",
                  )}
                >
                  <Badge tone={toneForSeverity(f.severity)} variant="soft" className="shrink-0">
                    {f.severity}
                  </Badge>
                  <span className="min-w-0 flex-1">
                    <span className="flex flex-wrap items-center gap-x-2 gap-y-1">
                      <span className="truncate text-sm font-medium text-text-primary">{f.title}</span>
                      <span className="text-code text-text-muted">{f.rule_id}</span>
                    </span>
                    <span className="mt-1 flex flex-wrap items-center gap-1.5">
                      {f.entity_refs.slice(0, 6).map((ref, i) => (
                        <span
                          key={i}
                          className="text-code rounded border border-border px-1.5 py-px text-text-muted"
                        >
                          {ref.type}:{ref.code}
                        </span>
                      ))}
                      {f.entity_refs.length > 6 && (
                        <span className="text-meta">+{f.entity_refs.length - 6} more</span>
                      )}
                    </span>
                  </span>
                  <span className="flex shrink-0 flex-col items-end gap-1.5">
                    <Badge tone={status.tone} size="sm" variant="outline">
                      {status.label}
                    </Badge>
                    <svg viewBox="0 0 16 16" aria-hidden="true" className="h-4 w-4 text-text-muted" fill="none">
                      <path d="m6 4 4 4-4 4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
                    </svg>
                  </span>
                </button>
              </li>
            );
          })}
        </ul>
      )}

      {selected && (
        <FindingDetail
          finding={selected}
          index={selectedIndex}
          total={filtered.length}
          onStep={step}
          onClose={() => setSelectedId(null)}
          explanation={explanationsByFinding[selected.id]}
          onToggleExplanation={() => void toggleExplanation(selected)}
          suggestions={suggestionsByFinding[selected.id]}
          onToggleSuggestions={() => void toggleSuggestions(selected)}
          onApplySuggestion={onApplySuggestion ? (c) => applySuggestion(selected, c) : undefined}
          applyingKey={applyingKey}
          busy={busyId === selected.id}
          reviewerError={reviewer.error}
          onAcceptRisk={() => void handleAcceptRisk(selected)}
          onReopen={() => void handleReopen(selected)}
          onProposeFix={onProposeFix ? () => onProposeFix(selected) : undefined}
        />
      )}
    </div>
  );
}

interface DetailProps {
  finding: Finding;
  index: number;
  total: number;
  onStep: (delta: number) => void;
  onClose: () => void;
  explanation?: ExplanationState;
  onToggleExplanation: () => void;
  suggestions?: SuggestionsResponse | "loading";
  onToggleSuggestions: () => void;
  onApplySuggestion?: (c: SuggestionCandidate) => void;
  applyingKey: string | null;
  busy: boolean;
  reviewerError: string | null;
  onAcceptRisk: () => void;
  onReopen: () => void;
  onProposeFix?: () => void;
}

/** Detail drawer with previous/next review controls: a 400-finding queue is
 *  worked through without returning to the list each time. */
function FindingDetail({
  finding,
  index,
  total,
  onStep,
  onClose,
  explanation,
  onToggleExplanation,
  suggestions,
  onToggleSuggestions,
  onApplySuggestion,
  applyingKey,
  busy,
  reviewerError,
  onAcceptRisk,
  onReopen,
  onProposeFix,
}: DetailProps) {
  const status = statusFor(finding);
  const accepted = finding.status === "ACCEPTED_RISK";

  return (
    <Drawer
      open
      onClose={onClose}
      title={finding.title}
      subtitle={finding.rule_id}
      scrim="none"
      meta={
        <>
          <Badge tone={toneForSeverity(finding.severity)} size="sm">
            {finding.severity}
          </Badge>
          <Badge tone={status.tone} size="sm" variant="outline">
            {status.label}
          </Badge>
        </>
      }
      footer={
        <div className="flex flex-wrap items-center gap-2">
          <div className="flex items-center gap-1">
            <Button size="sm" variant="ghost" onClick={() => onStep(-1)} title="Previous finding in the filtered list">
              ← Prev
            </Button>
            <span className="nums text-meta">
              {index + 1} / {total}
            </span>
            <Button size="sm" variant="ghost" onClick={() => onStep(1)} title="Next finding in the filtered list">
              Next →
            </Button>
          </div>
          <div className="ml-auto flex flex-wrap gap-2">
            {accepted ? (
              <Button size="sm" loading={busy} onClick={onReopen}>
                Reopen
              </Button>
            ) : (
              <Button size="sm" onClick={onAcceptRisk}>
                Mark as intentional
              </Button>
            )}
            {onProposeFix && (
              <Button size="sm" variant="primary" onClick={onProposeFix}>
                Propose a fix
              </Button>
            )}
          </div>
        </div>
      }
    >
      {reviewerError && (
        <Alert tone="warning" className="mb-3">
          {reviewerError}
        </Alert>
      )}

      {accepted && (
        <Alert tone="warning" className="mb-3" title="Accepted as intentional">
          Reviewed by {finding.reviewed_by}
          {finding.review_note ? ` - "${finding.review_note}"` : ""}
        </Alert>
      )}

      <div className="flex flex-col gap-3">
        <div className="flex flex-wrap gap-1.5">
          {finding.entity_refs.map((ref, i) => (
            <span key={i} className="text-code rounded border border-border bg-surface-sunken px-1.5 py-0.5 text-text-secondary">
              {ref.type}:{ref.code}
            </span>
          ))}
          {finding.slot_refs.map((slot, i) => (
            <span key={`slot-${i}`} className="text-code rounded border border-border bg-surface-sunken px-1.5 py-0.5 text-text-secondary">
              {slot.day_code} {slot.period_code}
            </span>
          ))}
        </div>

        <DetailSection
          title="Explanation"
          description="Plain-language summary from the local AI advisor - optional, never required to act"
          actions={
            <Button size="sm" onClick={onToggleExplanation}>
              {explanation ? "Hide" : "Explain"}
            </Button>
          }
        >
          {explanation?.status === "loading" && <p className="text-meta">Asking the local AI advisor…</p>}
          {explanation?.status === "error" && <Alert tone="critical">{explanation.message}</Alert>}
          {explanation?.status === "done" && <p className="text-body">{explanation.text}</p>}
          {!explanation && <p className="text-meta">Not summarized yet.</p>}
        </DetailSection>

        <DetailSection
          title="Suggested fixes"
          description="Validated alternatives that do not create a new clash"
          actions={
            <Button size="sm" onClick={onToggleSuggestions}>
              {suggestions ? "Hide" : "Suggest fixes"}
            </Button>
          }
        >
          {suggestions === "loading" && <p className="text-meta">Searching for valid alternatives…</p>}
          {suggestions && suggestions !== "loading" && (
            <>
              {!suggestions.supported && <p className="text-meta">{suggestions.note}</p>}
              {suggestions.supported && suggestions.candidates.length === 0 && (
                <p className="text-meta">No valid alternative found that doesn't create a new clash.</p>
              )}
              {suggestions.supported && suggestions.candidates.length > 0 && (
                <div className="flex max-h-72 flex-col gap-1.5 overflow-y-auto pr-1">
                  {suggestions.candidates.map((c, i) => {
                    const key = `${finding.id}:${c.entry_id}:${c.after.day_code}:${c.after.period_code}:${c.after.room_code}`;
                    return (
                      <SuggestionCandidateCard
                        key={i}
                        candidate={c}
                        onApply={onApplySuggestion ? () => onApplySuggestion(c) : undefined}
                        applying={applyingKey === key}
                      />
                    );
                  })}
                </div>
              )}
            </>
          )}
          {!suggestions && <p className="text-meta">Not searched yet.</p>}
        </DetailSection>

        <DetailSection title="Evidence" description="Exactly what the rules engine evaluated">
          <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-xs">
            {Object.entries(finding.evidence).map(([k, v]) => (
              <div key={k} className="contents">
                <dt className="text-text-muted">{k}</dt>
                <dd className="text-code break-all text-text-secondary">
                  {typeof v === "object" && v !== null ? JSON.stringify(v) : String(v)}
                </dd>
              </div>
            ))}
            {Object.keys(finding.evidence).length === 0 && (
              <p className="text-meta">No structured evidence recorded for this rule.</p>
            )}
          </dl>
        </DetailSection>

        <p className="text-meta">
          Detected {new Date(finding.computed_at).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" })} ·
          id {finding.id}
        </p>
      </div>
    </Drawer>
  );
}
