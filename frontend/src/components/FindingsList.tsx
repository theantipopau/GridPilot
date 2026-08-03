import type { Finding, Severity } from "../types";

interface Props {
  findings: Finding[];
  countsBySeverity: Record<Severity, number>;
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

export default function FindingsList({ findings, countsBySeverity }: Props) {
  if (findings.length === 0) {
    return (
      <div className="p-6">
        <p className="rounded-lg border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-800">
          No findings - the rules engine found no clashes in the current timetable.
        </p>
      </div>
    );
  }

  return (
    <div className="p-6">
      <div className="mb-4 flex gap-3 text-sm">
        {(["critical", "warning", "info"] as Severity[]).map((sev) => (
          <span key={sev} className={`rounded-full px-3 py-1 font-medium ${SEVERITY_BADGE[sev]}`}>
            {countsBySeverity[sev]} {sev}
          </span>
        ))}
      </div>
      <div className="flex flex-col gap-2">
        {findings.map((f) => (
          <div key={f.id} className={`rounded-lg border p-3 text-sm ${SEVERITY_STYLES[f.severity]}`}>
            <div className="flex items-center justify-between">
              <span className="font-medium">{f.title}</span>
              <span className="text-xs uppercase tracking-wide opacity-60">{f.rule_id}</span>
            </div>
            <div className="mt-1 flex flex-wrap gap-1">
              {f.entity_refs.map((ref, i) => (
                <span key={i} className="rounded border border-current/30 px-1.5 py-0.5 text-xs opacity-80">
                  {ref.type}:{ref.code}
                </span>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
