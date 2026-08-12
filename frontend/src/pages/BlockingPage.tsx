import { useEffect, useState } from "react";
import { fetchBlockingLines } from "../api";
import LoadingState from "../components/LoadingState";
import PageHeader from "../components/PageHeader";
import { IconColumns } from "../components/icons";
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
    return <td className="border-b border-l border-slate-100 p-2 text-center text-slate-200">·</td>;
  }
  if (cg.courses.length === 0) {
    return <td className="border-b border-l border-slate-100 p-2 text-xs text-slate-400">(no course)</td>;
  }
  return (
    <td className="border-b border-l border-slate-100 p-2 align-top text-xs">
      <div className="flex flex-col gap-1">
        {cg.courses.map((c, i) => (
          <div key={i}>
            <div className="font-medium text-slate-800">{c.class_name_code ?? "—"}</div>
            <div className="text-slate-500">
              {c.teacher_code ?? "—"} · {c.room_code ?? "no room"}
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
    <div>
      <h2 className="mb-2 text-sm font-semibold uppercase tracking-wide text-slate-500">
        Group {group.group}
      </h2>
      <div className="overflow-x-auto rounded-lg border border-slate-200">
        <table className="w-full border-collapse text-sm">
          <thead>
            <tr>
              <th className="w-24 border-b border-r border-slate-200 bg-slate-50 p-2 text-left text-xs font-medium text-slate-500">
                Roll class
              </th>
              {group.lines.map((line) => (
                <th
                  key={line.id}
                  className="min-w-[9rem] border-b border-l border-slate-200 bg-slate-50 p-2 text-left text-xs font-medium text-slate-500"
                >
                  <div className="text-slate-700">Line {line.line}</div>
                  <div className="font-normal normal-case text-slate-400">
                    {line.name ?? line.code ?? "(option line)"}
                  </div>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rollClasses.map((rc) => (
              <tr key={rc}>
                <td className="border-b border-r border-slate-200 p-2 text-xs font-medium text-slate-700">{rc}</td>
                {group.lines.map((line) => (
                  <Cell key={line.id} line={line} rollClassCode={rc} />
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export default function BlockingPage() {
  const [data, setData] = useState<BlockingLinesResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchBlockingLines().then(setData).catch((e) => setError(String(e)));
  }, []);

  if (error) return <div className="p-6 text-red-600">Failed to load blocking lines: {error}</div>;
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
          roll class's Fratelli/Assembly/Break slot, for example."
      />
      <div className="flex flex-col gap-8">
        {data.groups.map((group) => (
          <GroupTable key={group.group} group={group} />
        ))}
      </div>
    </div>
  );
}
