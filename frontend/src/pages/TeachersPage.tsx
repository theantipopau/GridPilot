import { useEffect, useState } from "react";
import { assignTeacherRole, createRole, fetchRoles, fetchTeachers, updateTeacherProfile } from "../api";
import LoadingState from "../components/LoadingState";
import { ReviewerField } from "../components/ReviewShell";
import { IconUsers } from "../components/icons";
import { useReviewerGate } from "../lib/reviewer";
import {
  Alert,
  Badge,
  Button,
  DataTable,
  DetailSection,
  Input,
  PageHeader,
  type DataTableColumn,
  type SortState,
} from "../ui";
import { cx } from "../ui/cx";
import type { CareerStage, RegistrationStatus, StaffRole, TeacherSummary } from "../types";

function formatMinutes(minutes: number | null): string {
  if (minutes == null) return "—";
  return `${Math.round(minutes)} min`;
}

const CAREER_STAGE_OPTIONS: CareerStage[] = ["GRADUATE", "EARLY_CAREER", "EXPERIENCED", "UNKNOWN"];
const REGISTRATION_STATUS_OPTIONS: RegistrationStatus[] = ["PROVISIONAL", "FULL", "UNKNOWN"];

/** Compact control inside a table cell: same focus ring, same border tokens,
 *  but sized to sit on one line with the row text. */
const CELL_SELECT =
  "max-w-[9.5rem] rounded-md border border-border-strong bg-surface px-1.5 py-1 text-xs text-text-primary " +
  "transition-[border-color,box-shadow] duration-150 focus:border-focus focus:outline-none " +
  "focus:shadow-[0_0_0_3px_color-mix(in_oklab,var(--color-focus)_22%,transparent)] disabled:opacity-50";

export default function TeachersPage() {
  const reviewer = useReviewerGate();
  const [teachers, setTeachers] = useState<TeacherSummary[] | null>(null);
  const [roles, setRoles] = useState<StaffRole[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [sort, setSort] = useState<SortState | null>({ key: "name", direction: "asc" });
  const [showRoleForm, setShowRoleForm] = useState(false);
  const [newRoleName, setNewRoleName] = useState("");
  const [newRoleTier, setNewRoleTier] = useState("");
  const [newRoleRelease, setNewRoleRelease] = useState("");
  const [savingRole, setSavingRole] = useState(false);
  const [assigningCode, setAssigningCode] = useState<string | null>(null);
  const [savingProfileCode, setSavingProfileCode] = useState<string | null>(null);

  const load = () => {
    fetchTeachers().then((r) => setTeachers(r.teachers)).catch((e) => setError(String(e)));
    fetchRoles().then((r) => setRoles(r.roles)).catch((e) => setError(String(e)));
  };

  useEffect(load, []);

  const handleCreateRole = async () => {
    if (!newRoleName.trim()) return;
    setSavingRole(true);
    setActionError(null);
    try {
      await createRole({
        name: newRoleName.trim(),
        tier: newRoleTier.trim() || undefined,
        release_minutes_per_cycle: newRoleRelease ? Number(newRoleRelease) : undefined,
      });
      setNewRoleName("");
      setNewRoleTier("");
      setNewRoleRelease("");
      setShowRoleForm(false);
      load();
    } catch (e) {
      setActionError(String(e));
    } finally {
      setSavingRole(false);
    }
  };

  const handleAssign = async (code: string, staffRoleId: string) => {
    if (!reviewer.check()) return;
    setAssigningCode(code);
    setActionError(null);
    try {
      await assignTeacherRole(code, staffRoleId ? Number(staffRoleId) : null, reviewer.reviewer);
      load();
    } catch (e) {
      setActionError(String(e));
    } finally {
      setAssigningCode(null);
    }
  };

  const handleProfileChange = async (
    teacher: TeacherSummary,
    changes: Partial<{
      registration_status: RegistrationStatus | null;
      career_stage: CareerStage | null;
      commenced_teaching_date: string | null;
      fte: number | null;
    }>,
  ) => {
    if (!reviewer.check()) return;
    setSavingProfileCode(teacher.code);
    setActionError(null);
    try {
      await updateTeacherProfile(teacher.code, {
        registration_status: teacher.profile?.registration_status ?? null,
        career_stage: teacher.profile?.career_stage ?? null,
        commenced_teaching_date: teacher.profile?.commenced_teaching_date ?? null,
        fte: teacher.profile?.fte ?? null,
        ...changes,
        updated_by: reviewer.reviewer,
      });
      load();
    } catch (e) {
      setActionError(String(e));
    } finally {
      setSavingProfileCode(null);
    }
  };

  if (!teachers || !roles) {
    return (
      <div className="p-6">
        {error ? (
          <Alert tone="critical" action={<Button size="sm" onClick={load}>Retry</Button>} onDismiss={() => setError(null)}>
            Failed to load teachers: {error}
          </Alert>
        ) : (
          <LoadingState label="Loading teachers…" />
        )}
      </div>
    );
  }

  const name = (t: TeacherSummary) => `${t.last_name}, ${t.first_name}`.toLowerCase();
  const sorted = sort
    ? [...teachers].sort((a, b) => {
        let cmp = 0;
        switch (sort.key) {
          case "name": cmp = name(a).localeCompare(name(b)); break;
          case "code": cmp = a.code.localeCompare(b.code); break;
          case "contracted": cmp = (a.contracted_load_minutes ?? -1) - (b.contracted_load_minutes ?? -1); break;
          case "scheduled": cmp = (a.scheduled_load_minutes ?? -1) - (b.scheduled_load_minutes ?? -1); break;
          default: cmp = 0;
        }
        return sort.direction === "asc" ? cmp : -cmp;
      })
    : teachers;

  const columns: DataTableColumn<TeacherSummary>[] = [
    {
      key: "name",
      header: "Name",
      sortable: true,
      render: (t) => <span className="font-medium text-text-primary">{t.last_name}, {t.first_name}</span>,
    },
    { key: "code", header: "Code", sortable: true, render: (t) => <span className="text-code">{t.code}</span> },
    {
      key: "faculty",
      header: "Faculty",
      hideBelow: "lg",
      render: (t) => t.faculty_codes.join(", ") || "—",
    },
    { key: "category", header: "Category", hideBelow: "lg", render: (t) => t.staff_category ?? "—" },
    {
      key: "contracted",
      header: "Contracted load",
      sortable: true,
      numeric: true,
      align: "right",
      hideBelow: "sm",
      render: (t) => formatMinutes(t.contracted_load_minutes),
    },
    {
      key: "scheduled",
      header: "Scheduled load",
      sortable: true,
      numeric: true,
      align: "right",
      hideBelow: "sm",
      render: (t) => {
        const over =
          t.contracted_load_minutes != null &&
          t.scheduled_load_minutes != null &&
          t.scheduled_load_minutes > t.contracted_load_minutes;
        if (t.scheduled_load_minutes == null) return "—";
        return (
          <span className="inline-flex items-center gap-1.5">
            <span className={over ? "font-medium text-warning" : undefined}>{formatMinutes(t.scheduled_load_minutes)}</span>
            {over && (
              <Badge tone="warning" size="sm" title="Scheduled load exceeds the contracted load">
                over
              </Badge>
            )}
          </span>
        );
      },
    },
    {
      key: "role",
      header: "Role",
      render: (t) => (
        <select
          value={t.role?.id ?? ""}
          disabled={assigningCode === t.code}
          aria-label={`Role for ${t.code}`}
          onChange={(e) => handleAssign(t.code, e.target.value)}
          className={CELL_SELECT}
        >
          <option value="">— none —</option>
          {roles.map((r) => (
            <option key={r.id} value={r.id}>
              {r.name}
              {r.tier ? ` (${r.tier})` : ""}
            </option>
          ))}
        </select>
      ),
    },
    {
      key: "career",
      header: "Career stage",
      hideBelow: "md",
      render: (t) => (
        <select
          value={t.profile?.career_stage ?? ""}
          disabled={savingProfileCode === t.code}
          aria-label={`Career stage for ${t.code}`}
          onChange={(e) => handleProfileChange(t, { career_stage: (e.target.value || null) as never })}
          className={cx(
            CELL_SELECT,
            t.profile?.career_stage === "EARLY_CAREER" &&
              "border-warning-border bg-warning-surface text-warning",
          )}
        >
          <option value="">— not set —</option>
          {CAREER_STAGE_OPTIONS.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
      ),
    },
    {
      key: "registration",
      header: "Registration",
      hideBelow: "md",
      render: (t) => (
        <select
          value={t.profile?.registration_status ?? ""}
          disabled={savingProfileCode === t.code}
          aria-label={`Registration status for ${t.code}`}
          onChange={(e) => handleProfileChange(t, { registration_status: (e.target.value || null) as never })}
          className={CELL_SELECT}
        >
          <option value="">— not set —</option>
          {REGISTRATION_STATUS_OPTIONS.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
      ),
    },
    {
      key: "fte",
      header: "FTE",
      hideBelow: "md",
      align: "right",
      render: (t) => (
        <input
          type="number"
          min={0.1}
          max={1}
          step={0.1}
          defaultValue={t.profile?.fte ?? ""}
          disabled={savingProfileCode === t.code}
          placeholder="1.0"
          aria-label={`FTE for ${t.code}`}
          onBlur={(e) => {
            const value = e.target.value ? Number(e.target.value) : null;
            if (value !== (t.profile?.fte ?? null)) handleProfileChange(t, { fte: value });
          }}
          className={cx(CELL_SELECT, "w-16 text-right")}
        />
      ),
    },
  ];

  return (
    <div className="p-6">
      <PageHeader
        icon={<IconUsers className="h-5 w-5" />}
        title="Teachers"
        description="Read-only from the imported .tfx (name, code, faculty, contracted load, scheduled load). Role/tier
          and career-stage profile are the only things entered here in GridPilot - neither has a source in any
          Timetabling Solutions export, and both survive a re-ingest because they're keyed by teacher code, not an
          internal id."
        meta={<span className="nums text-meta">{teachers.length} teachers · {roles.length} roles</span>}
        actions={<ReviewerField error={reviewer.error} />}
      />

      {(error || actionError) && (
        <Alert
          tone="critical"
          className="mb-4"
          onDismiss={() => {
            setError(null);
            setActionError(null);
          }}
        >
          {actionError ?? error}
        </Alert>
      )}

      <DetailSection
        className="mb-4"
        title="Roles / middle-leadership tiers"
        description={
          roles.length === 0
            ? "No roles defined yet - add one (e.g. Head of Department, Tier 1, release minutes per cycle) to start assigning them to teachers below."
            : undefined
        }
        actions={
          <Button size="sm" variant="secondary" onClick={() => setShowRoleForm((v) => !v)}>
            {showRoleForm ? "Cancel" : "+ New role"}
          </Button>
        }
      >
        {roles.length > 0 && (
          <div className="flex flex-wrap gap-1.5">
            {roles.map((r) => (
              <Badge key={r.id} tone="brand" variant="outline" size="sm">
                <span className="font-medium">{r.name}</span>
                {r.tier && <span className="text-text-muted">· {r.tier}</span>}
                {r.release_minutes_per_cycle != null && (
                  <span className="text-text-muted">· {formatMinutes(r.release_minutes_per_cycle)} release</span>
                )}
              </Badge>
            ))}
          </div>
        )}

        {showRoleForm && (
          <div className="mt-3 grid grid-cols-1 gap-2 border-t border-border pt-3 sm:grid-cols-4">
            <Input
              size="sm"
              containerClassName="sm:col-span-2"
              aria-label="Role name"
              placeholder="Role name (e.g. Head of Department)"
              value={newRoleName}
              onChange={(e) => setNewRoleName(e.target.value)}
            />
            <Input
              size="sm"
              aria-label="Tier"
              placeholder="Tier (e.g. Tier 1, optional)"
              value={newRoleTier}
              onChange={(e) => setNewRoleTier(e.target.value)}
            />
            <Input
              size="sm"
              type="number"
              aria-label="Release minutes per cycle"
              placeholder="Release min/cycle (optional)"
              value={newRoleRelease}
              onChange={(e) => setNewRoleRelease(e.target.value)}
            />
            <Button
              variant="primary"
              loading={savingRole}
              disabled={!newRoleName.trim()}
              className="sm:col-span-4"
              onClick={handleCreateRole}
            >
              {savingRole ? "Saving…" : "Save role"}
            </Button>
          </div>
        )}
      </DetailSection>

      <DataTable
        caption="Teachers with faculty, category, loads, role, career stage, registration and FTE"
        columns={columns}
        rows={sorted}
        rowKey={(t) => t.code}
        sort={sort}
        onSortChange={setSort}
        density="compact"
        emptyState={<p className="text-body text-text-secondary">No teachers loaded yet.</p>}
        className="max-h-[70vh]"
      />
    </div>
  );
}
