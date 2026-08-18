import { useEffect, useState } from "react";
import { assignTeacherRole, createRole, fetchRoles, fetchTeachers, updateTeacherProfile } from "../api";
import LoadingState from "../components/LoadingState";
import PageHeader from "../components/PageHeader";
import { IconUsers } from "../components/icons";
import type { CareerStage, RegistrationStatus, StaffRole, TeacherSummary } from "../types";

function formatMinutes(minutes: number | null): string {
  if (minutes == null) return "—";
  return `${Math.round(minutes)} min`;
}

const CAREER_STAGE_OPTIONS: CareerStage[] = ["GRADUATE", "EARLY_CAREER", "EXPERIENCED", "UNKNOWN"];
const REGISTRATION_STATUS_OPTIONS: RegistrationStatus[] = ["PROVISIONAL", "FULL", "UNKNOWN"];

export default function TeachersPage() {
  const [teachers, setTeachers] = useState<TeacherSummary[] | null>(null);
  const [roles, setRoles] = useState<StaffRole[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [reviewerName, setReviewerName] = useState("");
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
      setError(String(e));
    } finally {
      setSavingRole(false);
    }
  };

  const handleAssign = async (code: string, staffRoleId: string) => {
    if (!reviewerName.trim()) {
      setError("Enter your name (top right) before assigning a role.");
      return;
    }
    setAssigningCode(code);
    try {
      await assignTeacherRole(code, staffRoleId ? Number(staffRoleId) : null, reviewerName.trim());
      load();
    } catch (e) {
      setError(String(e));
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
    if (!reviewerName.trim()) {
      setError("Enter your name (top right) before editing a teacher's profile.");
      return;
    }
    setSavingProfileCode(teacher.code);
    try {
      await updateTeacherProfile(teacher.code, {
        registration_status: teacher.profile?.registration_status ?? null,
        career_stage: teacher.profile?.career_stage ?? null,
        commenced_teaching_date: teacher.profile?.commenced_teaching_date ?? null,
        fte: teacher.profile?.fte ?? null,
        ...changes,
        updated_by: reviewerName.trim(),
      });
      load();
    } catch (e) {
      setError(String(e));
    } finally {
      setSavingProfileCode(null);
    }
  };

  if (error) return <div className="p-6 text-red-600">{error}</div>;
  if (!teachers || !roles) return <LoadingState label="Loading teachers…" />;

  return (
    <div className="p-6">
      <PageHeader
        icon={<IconUsers className="h-5 w-5" />}
        title="Teachers"
        description="Read-only from the imported .tfx (name, code, faculty, contracted load, scheduled load). Role/tier
          and career-stage profile are the only things entered here in GridPilot - neither has a source in any
          Timetabling Solutions export, and both survive a re-ingest because they're keyed by teacher code, not an
          internal id."
        action={
          <input
            value={reviewerName}
            onChange={(e) => setReviewerName(e.target.value)}
            placeholder="Your name (for role assignment)"
            className="rounded-md border border-slate-300 px-2 py-1.5 text-sm"
          />
        }
      />

      <div className="mb-4 rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
        <div className="mb-2 flex items-center justify-between">
          <h3 className="text-sm font-semibold text-slate-700">Roles / middle-leadership tiers</h3>
          <button
            type="button"
            onClick={() => setShowRoleForm((v) => !v)}
            className="rounded-md border border-slate-300 px-2.5 py-1 text-xs font-medium text-slate-600 transition-colors duration-150 hover:bg-slate-50"
          >
            {showRoleForm ? "Cancel" : "+ New role"}
          </button>
        </div>

        {roles.length === 0 && !showRoleForm && (
          <p className="text-xs text-slate-400">
            No roles defined yet - add one (e.g. "Head of Department", Tier 1, release minutes per cycle) to start
            assigning them to teachers below.
          </p>
        )}

        {roles.length > 0 && (
          <div className="mb-2 flex flex-wrap gap-2">
            {roles.map((r) => (
              <span key={r.id} className="rounded-full border border-slate-200 bg-slate-50 px-2.5 py-1 text-xs text-slate-600">
                <span className="font-medium text-slate-800">{r.name}</span>
                {r.tier && <span className="ml-1 text-slate-400">· {r.tier}</span>}
                {r.release_minutes_per_cycle != null && (
                  <span className="ml-1 text-slate-400">· {formatMinutes(r.release_minutes_per_cycle)} release</span>
                )}
              </span>
            ))}
          </div>
        )}

        {showRoleForm && (
          <div className="mt-3 grid grid-cols-1 gap-2 border-t border-slate-100 pt-3 sm:grid-cols-4">
            <input
              value={newRoleName}
              onChange={(e) => setNewRoleName(e.target.value)}
              placeholder="Role name (e.g. Head of Department)"
              className="rounded border border-slate-300 px-2 py-1 text-sm sm:col-span-2"
            />
            <input
              value={newRoleTier}
              onChange={(e) => setNewRoleTier(e.target.value)}
              placeholder="Tier (e.g. Tier 1, optional)"
              className="rounded border border-slate-300 px-2 py-1 text-sm"
            />
            <input
              value={newRoleRelease}
              onChange={(e) => setNewRoleRelease(e.target.value)}
              placeholder="Release min/cycle (optional)"
              type="number"
              className="rounded border border-slate-300 px-2 py-1 text-sm"
            />
            <button
              type="button"
              onClick={handleCreateRole}
              disabled={!newRoleName.trim() || savingRole}
              className="rounded-md bg-sky-600 px-3 py-1.5 text-sm font-medium text-white transition-colors duration-150 hover:bg-sky-700 disabled:opacity-50 sm:col-span-4"
            >
              {savingRole ? "Saving…" : "Save role"}
            </button>
          </div>
        )}
      </div>

      <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white shadow-sm">
        <table className="w-full border-collapse text-sm">
          <thead>
            <tr className="border-b border-slate-200 bg-slate-50 text-left text-xs font-medium text-slate-500">
              <th className="p-2.5">Name</th>
              <th className="p-2.5">Code</th>
              <th className="p-2.5">Faculty</th>
              <th className="p-2.5">Category</th>
              <th className="p-2.5">Contracted load</th>
              <th className="p-2.5">Scheduled load</th>
              <th className="p-2.5">Role</th>
              <th className="p-2.5">Career stage</th>
              <th className="p-2.5">Registration</th>
              <th className="p-2.5">FTE</th>
            </tr>
          </thead>
          <tbody>
            {teachers.map((t) => {
              const over =
                t.contracted_load_minutes != null &&
                t.scheduled_load_minutes != null &&
                t.scheduled_load_minutes > t.contracted_load_minutes;
              const savingProfile = savingProfileCode === t.code;
              return (
                <tr key={t.code} className="border-b border-slate-100 last:border-0 hover:bg-slate-50">
                  <td className="p-2.5 font-medium text-slate-800">
                    {t.last_name}, {t.first_name}
                  </td>
                  <td className="p-2.5 text-slate-500">{t.code}</td>
                  <td className="p-2.5 text-slate-500">{t.faculty_codes.join(", ") || "—"}</td>
                  <td className="p-2.5 text-slate-500">{t.staff_category ?? "—"}</td>
                  <td className="p-2.5 text-slate-500">{formatMinutes(t.contracted_load_minutes)}</td>
                  <td className={`p-2.5 ${over ? "font-medium text-amber-700" : "text-slate-500"}`}>
                    {formatMinutes(t.scheduled_load_minutes)}
                  </td>
                  <td className="p-2.5">
                    <select
                      value={t.role?.id ?? ""}
                      disabled={assigningCode === t.code}
                      onChange={(e) => handleAssign(t.code, e.target.value)}
                      className="rounded border border-slate-300 px-1.5 py-1 text-xs text-slate-700 disabled:opacity-50"
                    >
                      <option value="">— none —</option>
                      {roles.map((r) => (
                        <option key={r.id} value={r.id}>
                          {r.name}
                          {r.tier ? ` (${r.tier})` : ""}
                        </option>
                      ))}
                    </select>
                  </td>
                  <td className="p-2.5">
                    <select
                      value={t.profile?.career_stage ?? ""}
                      disabled={savingProfile}
                      onChange={(e) => handleProfileChange(t, { career_stage: (e.target.value || null) as never })}
                      className={`rounded border px-1.5 py-1 text-xs disabled:opacity-50 ${
                        t.profile?.career_stage === "EARLY_CAREER"
                          ? "border-amber-300 bg-amber-50 text-amber-800"
                          : "border-slate-300 text-slate-700"
                      }`}
                    >
                      <option value="">— not set —</option>
                      {CAREER_STAGE_OPTIONS.map((s) => (
                        <option key={s} value={s}>
                          {s}
                        </option>
                      ))}
                    </select>
                  </td>
                  <td className="p-2.5">
                    <select
                      value={t.profile?.registration_status ?? ""}
                      disabled={savingProfile}
                      onChange={(e) => handleProfileChange(t, { registration_status: (e.target.value || null) as never })}
                      className="rounded border border-slate-300 px-1.5 py-1 text-xs text-slate-700 disabled:opacity-50"
                    >
                      <option value="">— not set —</option>
                      {REGISTRATION_STATUS_OPTIONS.map((s) => (
                        <option key={s} value={s}>
                          {s}
                        </option>
                      ))}
                    </select>
                  </td>
                  <td className="p-2.5">
                    <input
                      type="number"
                      min={0.1}
                      max={1}
                      step={0.1}
                      defaultValue={t.profile?.fte ?? ""}
                      disabled={savingProfile}
                      placeholder="1.0"
                      onBlur={(e) => {
                        const value = e.target.value ? Number(e.target.value) : null;
                        if (value !== (t.profile?.fte ?? null)) handleProfileChange(t, { fte: value });
                      }}
                      className="w-16 rounded border border-slate-300 px-1.5 py-1 text-xs text-slate-700 disabled:opacity-50"
                    />
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
