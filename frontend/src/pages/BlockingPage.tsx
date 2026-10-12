import { useEffect, useState } from "react";
import { fetchBlockingLines } from "../api";
import BlockingDemand from "../components/BlockingDemand";
import LoadingState from "../components/LoadingState";
import { IconColumns } from "../components/icons";
import { Alert, Badge, Button, PageHeader } from "../ui";
import type { BlockingGroup, BlockingLine, BlockingLinesResponse } from "../types";

function rollClassCodesInGroup(group: BlockingGroup): string[] {
  const codes = new Set<string>();
  for (const line of group.lines) {
    for (const cg of line.class_groups) codes.add(cg.roll_class_code);
  }
  return [...codes].sort();
}

function Cell({ line, rollClassCode }: { line: BlockingLine; rollClassCode: string }) {
  const cg = line.class_groups.find((c) => c.roll_class_code === rollClassCode);
  if (!cg) {
    return <td className="border-b border-l border-border p-2 text-center text-text-muted">·</td>;
  }
  if (cg.courses.length === 0) {
    return <td className="border-b border-l border-border p-2 text-xs text-text-muted">(no course)</td>;
  }
  return (
    <td className="border-b border-l border-border p-2 align-top text-xs">
      <div className="flex flex-col gap-1">
        {cg.courses.map((c, i) => (
          <div key={i}>
            <div className="font-medium text-text-primary">{c.class_name_code ?? "—"}</div>
            <div className="text-meta text-text-muted">
              {c.teacher_code ?? "—"} · {c.room_code ?? "no room"}
              {c.enrolled_count != null && <> · {c.enrolled_count} enrolled</>}
            </div>
          </div>
        ))}
      </div>
    </td>
  );
}

function GroupTable({ group }: { group: BlockingGroup }) {
  const rollClasses = rollClassCodesInGroup(group);

  return (
    <section>
      <h2 className="mb-2 text-section-title">Group {group.group}</h2>
      <div className="overflow-x-auto rounded-lg border border-border bg-surface">
        <table className="w-full border-collapse text-table">
          <thead>
            <tr>
              <th className="w-24 border-b border-r border-border bg-surface-sunken p-2 text-left text-label">
                Roll class
              </th>
              {group.lines.map((line) => (
                <th
                  key={line.id}
                  className="min-w-[9rem] border-b border-l border-border bg-surface-sunken p-2 text-left text-label"
                >
                  <div className="flex items-center gap-1.5 text-text-primary">
                    Line {line.line}
                    {line.open_finding_count > 0 && (
                      <Badge
                        tone="warning"
                        size="sm"
                        className="nums"
                        title={`${line.open_finding_count} open finding${line.open_finding_count === 1 ? "" : "s"} touch a class, teacher, or room on this line`}
                      >
                        {line.open_finding_count}
                      </Badge>
                    )}
                  </div>
                  <div className="font-normal text-text-muted">
                    {line.name ?? line.code ?? "(option line)"}
                  </div>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rollClasses.map((rc) => (
              <tr key={rc}>
                <td className="border-b border-r border-border p-2 text-xs font-medium text-text-secondary">{rc}</td>
                {group.lines.map((line) => (
                  <Cell key={line.id} line={line} rollClassCode={rc} />
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

export default function BlockingPage() {
  const [data, setData] = useState<BlockingLinesResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = () => {
    fetchBlockingLines().then(setData).catch((e) => setError(String(e)));
  };

  useEffect(load, []);

  if (error) {
    return (
      <div className="p-6">
        <Alert tone="critical" action={<Button size="sm" onClick={load}>Retry</Button>} onDismiss={() => setError(null)}>
          Failed to load blocking lines: {error}
        </Alert>
      </div>
    );
  }
  if (!data) return <LoadingState label="Loading the blocking pattern…" />;

  return (
    <div className="p-6">
      <PageHeader
        icon={<IconColumns className="h-5 w-5" />}
        title="Blocking"
        description="The option-line / blocking-pattern structure - which classes run in parallel so a student can pick
          one per line without a clash. Read-only: sourced from the .tfx's MRCGs, the same board a timetabler
          currently has to infer from a spreadsheet. A line with a name/code (e.g. '10 English') runs the same
          subject for every roll class; a blank one is a genuine option line where different subjects run in parallel.
          Each group's label is TTS's own internal grouping code, not always a year level - one group covers every
          roll class's Fratelli/Assembly/Break slot, for example. A line's badge counts open findings that touch a
          class, teacher, or room on it - which structures are actually producing the clashes the Findings page
          reports. Enrolled counts are shown as fact, not a judgement - a course reading 0 isn't necessarily
          under-subscribed, it may mean its roll class is routed through a different offering entirely."
        meta={<span className="nums text-meta">{data.groups.length} groups</span>}
      />
      <div className="flex flex-col gap-8">
        {data.groups.map((group) => (
          <GroupTable key={group.group} group={group} />
        ))}
      </div>

      <div className="mt-8">
        <BlockingDemand />
      </div>
    </div>
  );
}
