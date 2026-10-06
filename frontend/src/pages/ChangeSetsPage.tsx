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
import { ApprovalBadge } from "../components/ChangeSetStatus";
import EmptyState from "../components/EmptyState";
import LoadingState from "../components/LoadingState";
import { IconGitBranch, IconInbox } from "../components/icons";
import { Alert, Button, Input, PageHeader } from "../ui";
import { cx } from "../ui/cx";
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
  openChangeSetId?: number | null;
}

export default function ChangeSetsPage({ reference, proposeFixContext, onConsumeProposeFixContext, openChangeSetId }: Props) {
  const [list, setList] = useState<ChangeSetSummary[] | null>(null);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [detail, setDetail] = useState<ChangeSetDetailType | null>(null);
  const [newName, setNewName] = useState("");
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadList = () => {
    fetchChangeSets()
      .then((r) => setList(r.change_sets))
      .catch((e) => setError(String(e)));
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

  useEffect(() => {
    if (openChangeSetId != null) {
      setSelectedId(openChangeSetId);
      loadList();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [openChangeSetId]);

  const handleCreate = async () => {
    if (!newName.trim() || creating) return;
    setCreating(true);
    setError(null);
    try {
      const { id } = await createChangeSet(newName.trim(), undefined, "you");
      setNewName("");
      loadList();
      setSelectedId(id);
      if (proposeFixContext) onConsumeProposeFixContext();
    } catch (e) {
      setError(String(e));
    } finally {
      setCreating(false);
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
    <div className="p-6">
      <PageHeader
        icon={<IconGitBranch className="h-5 w-5" />}
        title="Change Sets"
        description="Proposed edits, validated against the clash rules before approval. The imported timetable is never mutated - approving a change set only creates a durable record."
      />

      {error && (
        <Alert tone="critical" className="mb-4" onDismiss={() => setError(null)}>
          {error}
        </Alert>
      )}

      {proposeFixContext && !detail && (
        <Alert tone="info" className="mb-4" title="Create a change set to propose a fix for this finding">
          <div className="mt-2 flex flex-wrap items-end gap-2">
            <Input
              size="sm"
              containerClassName="w-64"
              aria-label="New change set name"
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
            />
            <Button size="sm" variant="primary" loading={creating} onClick={handleCreate}>
              Create
            </Button>
          </div>
        </Alert>
      )}

      <div className="flex flex-col items-start gap-6 lg:flex-row">
        <aside className="w-full shrink-0 lg:w-72">
          {!proposeFixContext && (
            <div className="mb-3 flex items-end gap-1.5">
              <Input
                size="sm"
                containerClassName="flex-1"
                label="New change set"
                placeholder="Name it, e.g. Mass repair (8 moves)"
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") handleCreate();
                }}
              />
              <Button size="sm" variant="primary" loading={creating} onClick={handleCreate} disabled={!newName.trim()}>
                Create
              </Button>
            </div>
          )}

          {list == null ? (
            <LoadingState label="Loading change sets…" />
          ) : list.length === 0 ? (
            <EmptyState
              icon={<IconInbox className="h-7 w-7" />}
              title="No change sets yet"
              description="Create one to propose and validate timetable moves."
            />
          ) : (
            <ul className="flex flex-col gap-1.5" aria-label="Change sets">
              {list.map((cs) => (
                <li key={cs.id}>
                  <button
                    type="button"
                    aria-current={selectedId === cs.id ? "true" : undefined}
                    onClick={() => setSelectedId(cs.id)}
                    className={cx(
                      "w-full rounded-lg border p-2.5 text-left transition-colors duration-150",
                      "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus",
                      selectedId === cs.id
                        ? "border-brand bg-brand-surface"
                        : "border-border bg-surface hover:border-border-strong hover:bg-hovered",
                    )}
                  >
                    <span className="flex items-center justify-between gap-2">
                      <span className="min-w-0 truncate text-sm font-medium text-text-primary">{cs.name}</span>
                      <ApprovalBadge status={cs.approval_status} />
                    </span>
                    <span className="nums mt-0.5 block text-meta">
                      {cs.change_count} change{cs.change_count === 1 ? "" : "s"}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </aside>

        <div className="min-w-0 flex-1">
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
            <EmptyState
              icon={<IconGitBranch className="h-7 w-7" />}
              title="Select a change set"
              description="Pick one from the list, or create one to propose a fix."
            />
          )}
        </div>
      </div>
    </div>
  );
}
