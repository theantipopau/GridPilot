import { useEffect, useState } from "react";
import {
  addProposedChange,
  approveChangeSet,
  createChangeSet,
  fetchChangeSet,
  fetchChangeSets,
  rejectChangeSet,
  removeProposedChange,
  validateChangeSet,
} from "../api";
import ChangeSetDetail, { type AddChangeParams } from "../components/ChangeSetDetail";
import type { ChangeSetDetail as ChangeSetDetailType, ChangeSetSummary, ReferenceData } from "../types";

export interface ProposeFixContext {
  findingId: number;
  suggestedName: string;
  dayCode?: string;
  periodCode?: string;
  teacherCode?: string;
  roomCode?: string;
  classCode?: string;
}

interface Props {
  reference: ReferenceData;
  proposeFixContext: ProposeFixContext | null;
  onConsumeProposeFixContext: () => void;
}

const STATUS_COLORS: Record<string, string> = {
  DRAFT: "bg-slate-200 text-slate-700",
  APPROVED: "bg-emerald-600 text-white",
  REJECTED: "bg-slate-400 text-white",
};

export default function ChangeSetsPage({ reference, proposeFixContext, onConsumeProposeFixContext }: Props) {
  const [list, setList] = useState<ChangeSetSummary[] | null>(null);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [detail, setDetail] = useState<ChangeSetDetailType | null>(null);
  const [newName, setNewName] = useState("");
  const [error, setError] = useState<string | null>(null);

  const loadList = () => {
    fetchChangeSets().then((r) => setList(r.change_sets)).catch((e) => setError(String(e)));
  };

  useEffect(loadList, []);

  useEffect(() => {
    if (selectedId == null) {
      setDetail(null);
      return;
    }
    fetchChangeSet(selectedId).then(setDetail).catch((e) => setError(String(e)));
  }, [selectedId]);

  useEffect(() => {
    if (proposeFixContext) {
      setNewName(proposeFixContext.suggestedName);
    }
  }, [proposeFixContext]);

  const handleCreate = async () => {
    if (!newName.trim()) return;
    try {
      const { id } = await createChangeSet(newName.trim(), undefined, "you");
      setNewName("");
      loadList();
      setSelectedId(id);
      if (proposeFixContext) onConsumeProposeFixContext();
    } catch (e) {
      setError(String(e));
    }
  };

  const refreshDetail = async () => {
    if (selectedId != null) setDetail(await fetchChangeSet(selectedId));
    loadList();
  };

  const handleAddChange = async (params: AddChangeParams) => {
    if (selectedId == null) return;
    await addProposedChange(selectedId, params);
    await refreshDetail();
  };

  if (error) return <div className="p-6 text-red-600">{error}</div>;

  const prefill = proposeFixContext
    ? {
        day_code: proposeFixContext.dayCode,
        period_code: proposeFixContext.periodCode,
        teacher_code: proposeFixContext.teacherCode,
        room_code: proposeFixContext.roomCode,
        class_code: proposeFixContext.classCode,
        finding_id: proposeFixContext.findingId,
      }
    : undefined;

  return (
    <div className="flex gap-6 p-6">
      <div className="w-72 shrink-0">
        {proposeFixContext && !detail && (
          <div className="mb-3 rounded-lg border border-sky-200 bg-sky-50 p-3 text-sm">
            <p className="mb-2 text-sky-800">Create a change set to propose a fix for this finding:</p>
            <input
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              className="mb-2 w-full rounded border border-slate-300 px-2 py-1 text-sm"
            />
            <button type="button" onClick={handleCreate} className="rounded-md bg-sky-600 px-3 py-1 text-xs font-medium text-white">
              Create
            </button>
          </div>
        )}

        <div className="mb-2 flex items-center justify-between">
          <h3 className="text-sm font-semibold text-slate-700">Change sets</h3>
        </div>
        {!proposeFixContext && (
          <div className="mb-3 flex gap-1">
            <input
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              placeholder="New change set name"
              className="w-full rounded border border-slate-300 px-2 py-1 text-xs"
            />
            <button type="button" onClick={handleCreate} className="shrink-0 rounded bg-slate-700 px-2 py-1 text-xs text-white">
              +
            </button>
          </div>
        )}
        <div className="flex flex-col gap-1">
          {list?.map((cs) => (
            <button
              key={cs.id}
              type="button"
              onClick={() => setSelectedId(cs.id)}
              className={`rounded border p-2 text-left text-xs ${
                selectedId === cs.id ? "border-sky-400 bg-sky-50" : "border-slate-200 bg-white hover:bg-slate-50"
              }`}
            >
              <div className="flex items-center justify-between">
                <span className="font-medium text-slate-800">{cs.name}</span>
                <span className={`rounded-full px-1.5 py-0.5 text-[10px] ${STATUS_COLORS[cs.approval_status]}`}>
                  {cs.approval_status}
                </span>
              </div>
              <div className="text-slate-400">{cs.change_count} change(s)</div>
            </button>
          ))}
          {list?.length === 0 && <p className="text-xs text-slate-400">No change sets yet.</p>}
        </div>
      </div>

      <div className="flex-1">
        {detail ? (
          <ChangeSetDetail
            changeSet={detail}
            reference={reference}
            prefill={prefill}
            onAddChange={handleAddChange}
            onRemoveChange={async (changeId) => {
              await removeProposedChange(detail.id, changeId);
              await refreshDetail();
            }}
            onValidate={async () => {
              await validateChangeSet(detail.id);
              await refreshDetail();
            }}
            onApprove={async (reviewedBy) => {
              await approveChangeSet(detail.id, reviewedBy);
              await refreshDetail();
            }}
            onReject={async (reviewedBy) => {
              await rejectChangeSet(detail.id, reviewedBy);
              await refreshDetail();
            }}
          />
        ) : (
          <p className="text-sm text-slate-400">Select a change set, or create one to propose a fix.</p>
        )}
      </div>
    </div>
  );
}
